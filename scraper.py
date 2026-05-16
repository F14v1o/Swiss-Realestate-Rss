"""
ImmoMenu News Scraper

Runs via GitHub Actions twice daily. Fetches news from configured sources
(RSS feeds + HTML listings), sends each item to Claude for relevance scoring,
summarization and tagging, and writes relevant articles into the Supabase DB.

Security: Uses a dedicated scraper_bot DB user with minimal privileges
(SELECT + INSERT on the news table only — no auth access, no other tables).

Environment variables (injected from GitHub Secrets):
    SCRAPER_DB_URL      — postgresql://scraper_bot:pw@host:5432/postgres
    ANTHROPIC_API_KEY   — sk-ant-...

Local testing:
    export SCRAPER_DB_URL="postgresql://..."
    export ANTHROPIC_API_KEY="sk-ant-..."
    python scraper.py
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

import feedparser
import psycopg2
import requests
from anthropic import Anthropic
from bs4 import BeautifulSoup

from sources import (
    ALLOWED_TAGS,
    CLAUDE_MODEL,
    MAX_ITEMS_PER_SOURCE,
    MIN_RELEVANCE_SCORE,
    SOURCES,
)

# --- Configuration from environment ---
DB_URL = os.environ.get("SCRAPER_DB_URL")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY")

if not DB_URL or not ANTHROPIC_KEY:
    print("ERROR: SCRAPER_DB_URL or ANTHROPIC_API_KEY not set.")
    sys.exit(1)

claude = Anthropic(api_key=ANTHROPIC_KEY)

# Polite User-Agent — many servers block anonymous scrapers
USER_AGENT = (
    "Mozilla/5.0 (compatible; ImmoMenuNewsBot/1.0; "
    "+https://[YOUR-DOMAIN]/news)"
)
HEADERS = {"User-Agent": USER_AGENT}


# --- Database Helpers ---

def get_db_connection():
    """Opens a new DB connection. Short-lived — scraper runs 1–3 minutes."""
    return psycopg2.connect(DB_URL, connect_timeout=10)


def url_exists(url: str) -> bool:
    """Returns True if a URL is already stored in the DB (dedup guard)."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("select 1 from news where source_url = %s", (url,))
            return cur.fetchone() is not None
    finally:
        conn.close()


def insert_news(item: dict) -> bool:
    """Inserts a news item. ON CONFLICT handles race conditions gracefully."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into news (
                    source, source_url, title, summary, original_excerpt,
                    tags, relevance_score, published_at
                ) values (%s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (source_url) do nothing
                returning id
                """,
                (
                    item["source"],
                    item["source_url"],
                    item["title"],
                    item.get("summary"),
                    item.get("original_excerpt"),
                    item.get("tags", []),
                    item.get("relevance_score"),
                    item.get("published_at"),
                ),
            )
            inserted = cur.fetchone() is not None
            conn.commit()
            return inserted
    except Exception as e:
        conn.rollback()
        print(f"  DB insert error: {e}")
        return False
    finally:
        conn.close()


# --- HTTP Helper ---

def fetch_url(url: str, timeout: int = 30) -> str | None:
    """Fetches the HTML of a page. Returns None on any error."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r.text
    except requests.RequestException as e:
        print(f"  Fetch error {url}: {e}")
        return None


# --- RSS Scraping ---

def scrape_rss(source: dict) -> list[dict]:
    """Parses an RSS/Atom feed and returns a list of item dicts."""
    print(f"\n→ RSS feed: {source['name']}")
    try:
        feed = feedparser.parse(source["url"], agent=USER_AGENT)
    except Exception as e:
        print(f"  Feed parse error: {e}")
        return []

    if feed.bozo and not feed.entries:
        print(f"  Feed appears broken: {feed.bozo_exception}")
        return []

    items = []
    for entry in feed.entries[:MAX_ITEMS_PER_SOURCE]:
        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()
        if not title or not link:
            continue

        # Pull description/summary from the feed entry
        excerpt = entry.get("summary", "") or entry.get("description", "")
        if excerpt:
            # Strip HTML tags from feed description
            excerpt = BeautifulSoup(excerpt, "html.parser").get_text(
                separator=" ", strip=True
            )[:1500]

        items.append({
            "source": source["name"],
            "source_url": link,
            "title": title,
            "feed_excerpt": excerpt,
        })

    print(f"  Found: {len(items)} items")
    return items


# --- HTML Scraping ---

def scrape_html_listing(source: dict) -> list[dict]:
    """Fetches article links from an HTML listing page using CSS selectors."""
    print(f"\n→ HTML listing: {source['name']}")
    html = fetch_url(source["url"])
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    items = []
    seen_urls = set()  # Dedup within the page

    for link in soup.select(source["item_selector"]):
        href = link.get("href", "").strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue

        # Resolve relative URLs
        if href.startswith("/"):
            href = source["base_url"] + href
        elif not href.startswith("http"):
            continue  # Skip mailto:, tel:, etc.

        title = link.get_text(strip=True)
        if not title or len(title) < 10:
            continue  # Too short — likely not a news headline

        if href in seen_urls:
            continue
        seen_urls.add(href)

        items.append({
            "source": source["name"],
            "source_url": href,
            "title": title,
        })

        if len(items) >= MAX_ITEMS_PER_SOURCE:
            break

    print(f"  Found: {len(items)} items")
    return items


def fetch_article_text(url: str, article_selector: str | None = None) -> str:
    """Fetches and extracts the body text of an article page."""
    html = fetch_url(url)
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    # Remove boilerplate elements
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    if article_selector:
        container = soup.select_one(article_selector)
        if container:
            return container.get_text(separator=" ", strip=True)[:5000]

    # Fallback: full body text, truncated
    return soup.get_text(separator=" ", strip=True)[:5000]


# --- AI Enrichment ---

def enrich_with_claude(item: dict, article_text: str) -> dict | None:
    """
    Sends an article to Claude for relevance scoring, summarization and tagging.

    Returns the enriched item dict, or None if the item should be discarded.
    """
    if not article_text or len(article_text) < 100:
        print(f"  Skip (too little content): {item['title'][:60]}")
        return None

    tags_csv = ", ".join(ALLOWED_TAGS)

    prompt = f"""You are an editor for a Swiss real estate platform.

Target audience: Swiss homeowners 50+, often first-time sellers, non-technical.
Tone: "With you, not at you" — clear, jargon-free, helpful, authoritative.

Analyse the following news article for relevance and summarise it:

TITLE: {item["title"]}

CONTENT: {article_text}

Respond ONLY in the following JSON format. No markdown, no code fences,
no surrounding text — raw JSON only:

{{
  "relevance_score": <integer 1-10, how relevant for Swiss homeowners/sellers>,
  "summary": "<2-3 sentences in German: what happened and what it means CONCRETELY for homeowners — no jargon>",
  "tags": ["<tag1>", "<tag2>"]
}}

Tags MUST be chosen exclusively from this list: {tags_csv}
Return an empty array if no tags apply.

Relevance score guide:
- 1-3: Irrelevant (internal association news, unrelated politics, advertising)
- 4-5: Borderline (general economy, tangentially related)
- 6-7: Relevant (market trends, new regulations)
- 8-10: Highly relevant (tax changes, ownership legislation, concrete market data)
"""

    try:
        response = claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()

        # Defensively strip markdown fences if Claude adds them
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        data = json.loads(raw)

        # Validate and sanitize output
        score = int(data.get("relevance_score", 0))
        summary = str(data.get("summary", "")).strip()
        tags = data.get("tags", [])
        if not isinstance(tags, list):
            tags = []
        # Only allow tags from the controlled vocabulary
        tags = [t for t in tags if t in ALLOWED_TAGS]

        if not summary:
            print(f"  Skip (empty summary): {item['title'][:60]}")
            return None

        item["relevance_score"] = score
        item["summary"] = summary
        item["tags"] = tags
        return item

    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}")
        print(f"    Response was: {raw[:200]}")
        return None
    except Exception as e:
        print(f"  Claude error: {e}")
        return None


# --- Main Pipeline ---

def process_item(item: dict, source: dict, stats: dict):
    """Runs a single news item through the full enrichment and storage pipeline."""

    # 1. Deduplication check
    if url_exists(item["source_url"]):
        stats["already_exists"] += 1
        return

    print(f"\n  Processing: {item['title'][:70]}")

    # 2. Obtain article text
    # RSS feeds often include a description — use it as the base.
    # If it's too thin, fetch the full article page.
    article_text = item.get("feed_excerpt", "")

    if not article_text or len(article_text) < 300:
        fetched = fetch_article_text(
            item["source_url"], source.get("article_selector")
        )
        if fetched:
            article_text = fetched

    item["original_excerpt"] = article_text[:300] if article_text else ""

    # 3. AI enrichment
    enriched = enrich_with_claude(item, article_text)
    if not enriched:
        stats["errors"] += 1
        return

    # 4. Relevance filter
    if enriched["relevance_score"] < MIN_RELEVANCE_SCORE:
        print(
            f"  Skip (score {enriched['relevance_score']}): "
            f"{item['title'][:60]}"
        )
        stats["irrelevant"] += 1
        return

    # 5. Write to database
    enriched["published_at"] = datetime.now(timezone.utc)
    if insert_news(enriched):
        print(
            f"  ✓ Saved (score {enriched['relevance_score']}, "
            f"tags: {enriched['tags']})"
        )
        stats["new"] += 1
    else:
        stats["errors"] += 1


def main():
    print(f"=== ImmoMenu Scraper run {datetime.now().isoformat()} ===")

    stats = {
        "found": 0,
        "already_exists": 0,
        "irrelevant": 0,
        "errors": 0,
        "new": 0,
    }

    for source in SOURCES:
        try:
            source_type = source.get("type", "html")
            if source_type == "rss":
                items = scrape_rss(source)
            elif source_type == "html":
                items = scrape_html_listing(source)
            else:
                print(f"Unknown source type: {source_type}")
                continue

            stats["found"] += len(items)
        except Exception as e:
            print(f"Error processing source {source['name']}: {e}")
            continue

        for item in items:
            try:
                process_item(item, source, stats)
                # Brief delay — polite to sources and avoids API rate bursts
                time.sleep(1)
            except Exception as e:
                print(f"  Item error: {e}")
                stats["errors"] += 1

    print("\n=== Summary ===")
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print("================")


if __name__ == "__main__":
    main()
