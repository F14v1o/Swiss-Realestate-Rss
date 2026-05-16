# ImmoMenu AI Newsroom — Automated Real Estate Intelligence Pipeline

> **A fully automated, AI-powered news intelligence system built for a Swiss real estate platform.**  
> Collects, filters, enriches, and publishes industry-relevant news — twice daily, hands-free.

---

## Project Vision

The Swiss real estate market moves fast. Legislation changes, interest rates shift, tax rulings land — and staying on top of it all while running a client-facing business is genuinely hard.

This project is the foundation of an **AI-powered internal newsroom**: a system that monitors authoritative Swiss sources around the clock, filters noise with Claude AI, and surfaces only what matters to homeowners, sellers, and real estate professionals.

The same curated content feeds multiple downstream use cases simultaneously — from client briefings to social media to SEO — without any manual work after setup.

---

## The Bigger Picture: Three-Layer Intelligence Architecture

This scraper is **Layer 2** of a planned three-layer data intelligence stack:

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 1 — Hard Data (Monthly)                                  │
│  ─────────────────────────────────────────────────────────────  │
│  Source: FPRE Metaanalysis (Macro + Real Estate Reports, PDF)   │
│  Flow:   PDF delivered → AI parses → HTML page generated →      │
│          published to website + monthly newsletter sent         │
│  Cadence: Once per month, fully automated                       │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 2 — Current News (Daily) ← THIS PROJECT                  │
│  ─────────────────────────────────────────────────────────────  │
│  Source: Swiss news sites via RSS + HTML scraping               │
│  Flow:   Fetch → Claude filters & summarizes → DB → Website     │
│  Cadence: Twice daily via GitHub Actions                        │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 3 — Micro Data (Planned)                                 │
│  ─────────────────────────────────────────────────────────────  │
│  Source: Granular market data, transaction-level signals        │
│  Flow:   TBD — to be scoped after Layer 1 + 2 are stable        │
│  Cadence: TBD                                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Why We Built This

### The Problem
A real estate advisory business needs to be constantly informed — about market conditions, legal changes, tax rulings, interest rate shifts, and regulatory updates. Manually checking multiple news sources, association bulletins, and government announcements every day is unsustainable.

### The Solution
An automated pipeline that does the monitoring, filtering, summarization, and publishing — so the team wakes up to a curated briefing rather than a tab-crawling session.

### What It Unlocks

| Use Case | How It Works |
|---|---|
| **Internal Market Briefing** | Team reads a concise daily digest of what changed and what it means for clients |
| **Newsletter Content** | Curated summaries go directly into client-facing newsletters with minimal editing |
| **Social Media Ideas** | Each article generates content angles for Instagram Reels, Stories, and LinkedIn posts |
| **Client Conversations** | Advisors always have current, relevant talking points ready |
| **Website / SEO** | News cards published to `/news` build a long-term archive of relevant content |
| **Office Display** | Future: live news ticker on office screen for ambient market awareness |

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                    GitHub Actions (Cron)                      │
│              Runs at 06:00 + 18:00 UTC daily                 │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                      scraper.py                              │
│                                                              │
│  1. Fetch items from configured sources                      │
│     ├── RSS feeds (feedparser)                               │
│     └── HTML listings (BeautifulSoup)                        │
│                                                              │
│  2. Deduplicate against existing DB entries                  │
│                                                              │
│  3. Fetch full article text (when feed excerpt is thin)      │
│                                                              │
│  4. Send to Claude API for enrichment:                       │
│     ├── Relevance score (1–10)                               │
│     ├── Plain-language summary (2–3 sentences, German)       │
│     └── Tag classification (from controlled vocabulary)      │
│                                                              │
│  5. Filter: only items scoring ≥ MIN_RELEVANCE_SCORE         │
│                                                              │
│  6. Insert into Supabase via dedicated scraper_bot user      │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                   Supabase (PostgreSQL)                       │
│                                                              │
│  Table: news                                                 │
│  ├── source, source_url (unique), title                      │
│  ├── summary, original_excerpt                               │
│  ├── tags[], relevance_score                                 │
│  ├── published_at, scraped_at                                │
│  └── is_published, in_newsletter                             │
│                                                              │
│  Access: RLS enabled — public read, scraper_bot write only   │
└─────────────────────────┬────────────────────────────────────┘
                          │
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                  Frontend (/news)                            │
│                                                              │
│  Responsive news card grid                                   │
│  ├── Filter by tag (multi-select)                            │
│  ├── Sorted by published_at DESC                             │
│  └── Links out to source articles                            │
└──────────────────────────────────────────────────────────────┘
```

---

## Technology Stack

| Component | Technology | Notes |
|---|---|---|
| Orchestration | GitHub Actions | Free tier sufficient; 2× daily cron |
| Language | Python 3.11 | Clean, minimal dependencies |
| RSS Parsing | feedparser | Handles RSS 2.0 + Atom reliably |
| HTML Scraping | BeautifulSoup4 | CSS selector-based link extraction |
| HTTP | requests | With polite User-Agent header |
| AI Enrichment | Anthropic Claude API | Model configurable in `sources.py` |
| Database | Supabase (PostgreSQL) | Row Level Security enabled |
| DB Driver | psycopg2-binary | Direct PostgreSQL connection |
| Frontend |  Reads from Supabase directly |

**Estimated monthly cost:** ~5–15 CHF (Claude API tokens only; everything else is free tier)

---

## Repository Structure

```
immomenu-news-scraper/
├── scraper.py          # Main pipeline logic
├── sources.py          # Source configuration + AI parameters
├── requirements.txt    # Python dependencies (pinned versions)
└── .github/
    └── workflows/
        └── scraper.yml # GitHub Actions workflow definition
```

---

## Source Configuration (`sources.py`)

Sources are defined in a simple list. Two types are supported:

**RSS Feed (preferred — more robust):**
```python
{
    "name": "Source Display Name",
    "type": "rss",
    "url": "https://example.com/feed.xml",
}
```

**HTML Listing (CSS selector-based):**
```python
{
    "name": "Source Display Name",
    "type": "html",
    "url": "https://example.com/news",
    "item_selector": "h3 a",        # CSS selector for article links
    "base_url": "https://example.com",
    "article_selector": None,        # Optional: scopes full-text fetch
}
```

Adding a new source is a single commit. The next scheduled run picks it up automatically.

---

## AI Enrichment Logic

Each news item is sent to Claude with the following instructions:

- **Audience context:** Swiss homeowners 50+, often first-time sellers, non-technical
- **Tone directive:** Clear, jargon-free, actionable — "with you, not at you"
- **Output (JSON):**
  - `relevance_score` — integer 1–10
  - `summary` — 2–3 sentences in German explaining what happened and what it means for homeowners
  - `tags` — subset of a controlled vocabulary (see below)

**Relevance scoring guide:**

| Score | Meaning |
|---|---|
| 1–3 | Irrelevant (internal association news, unrelated politics, advertising) |
| 4–5 | Borderline (general economy, loosely related) |
| 6–7 | Relevant (market trends, new regulations) |
| 8–10 | Highly relevant (tax changes, ownership laws, concrete market data) |

Only items scoring `≥ MIN_RELEVANCE_SCORE` (default: 6) are written to the database.

**Controlled tag vocabulary:**

```
eigenmietwert · mietrecht · steuern · marktpreise · bauen · sanieren
energie · hypotheken · recht · verkauf · kauf · politik
stockwerkeigentum · grundstueckgewinnsteuer · erbrecht · wohneigentum · vermieten
```

Claude is instructed to select only from this list, ensuring consistent filtering and frontend tag buttons always work.

---

## Database Schema

```sql
create table news (
  id               uuid primary key default gen_random_uuid(),
  source           text        not null,
  source_url       text        not null unique,
  title            text        not null,
  summary          text,
  original_excerpt text,
  tags             text[],
  relevance_score  int,
  published_at     timestamp,
  scraped_at       timestamp   default now(),
  in_newsletter    boolean     default false,
  is_published     boolean     default true
);
```

**Security model:**
- Row Level Security (RLS) enabled — the public frontend can only `SELECT` rows where `is_published = true`
- A dedicated `scraper_bot` database user has `SELECT + INSERT` rights on the `news` table only
- No access to auth tables, no other schema access

---

## GitHub Actions Workflow

```yaml
on:
  schedule:
    - cron: '0 6,18 * * *'   # 06:00 + 18:00 UTC
  workflow_dispatch:           # Manual trigger available
```

Secrets required (stored in GitHub → Settings → Secrets):

| Secret | Description |
|---|---|
| `SCRAPER_DB_URL` | PostgreSQL connection string for `scraper_bot` user |
| `ANTHROPIC_API_KEY` | Anthropic API key (`sk-ant-...`) |

No secrets are hardcoded anywhere in the codebase.

---

## Setup Overview (for replication)

1. **Supabase** — Run the schema SQL, create the `scraper_bot` user with a strong password, apply grants
2. **Build connection string** — `postgresql://scraper_bot:PASSWORD@host:5432/postgres`
3. **Anthropic API** — Create a key, add billing credit
4. **GitHub repo** — Private repository, add the four files
5. **GitHub Secrets** — Add `SCRAPER_DB_URL` + `ANTHROPIC_API_KEY`
6. **First run** — Trigger manually from Actions tab, verify logs + Supabase table
7. **Frontend** — Create a /news section, which reads from the "news table" created

Full step-by-step setup documentation is maintained separately (not published here for security reasons).

---

## Extending the Pipeline

### Adding Sources
Edit `sources.py`, add an entry, commit. Done. The selector for HTML sources can be found by right-clicking a news headline in the browser → "Inspect" → identifying the CSS pattern.

### Adjusting AI Sensitivity
In `sources.py`:
- `MIN_RELEVANCE_SCORE` — raise to be more selective, lower to be more inclusive
- `MAX_ITEMS_PER_SOURCE` — cap per source per run (prevents large first-run API spend)
- `CLAUDE_MODEL` — swap to Haiku for lower cost, Opus for higher quality

### Planned Extensions
- **Layer 1 Pipeline** — Monthly PDF ingestion (FPRE market reports) → AI parsing → HTML page generation + newsletter dispatch via Resend
- **Layer 3 Micro-Data** — Granular transaction and market signal data (scope TBD)
- **Weekly Newsletter** — Pulls the week's top-scored items from DB, builds HTML email, sends automatically
- **Office Display** — Live news ticker for ambient awareness in the office

---

## Error Handling

The scraper is designed to fail gracefully:

- Per-item try/catch — one broken article never crashes the full run
- `ON CONFLICT DO NOTHING` on DB insert — race conditions handled
- Claude response validation — malformed JSON is caught and logged, not raised
- Timeout on HTTP fetches — stuck requests don't block the pipeline
- Summary stats printed at end of every run for easy log monitoring

**Common issues and resolutions:**

| Error | Fix |
|---|---|
| `password authentication failed` | Check connection string, avoid special characters in password |
| `Could not translate host name` | Typo in DB URL — re-copy from Supabase dashboard |
| `anthropic.AuthenticationError 401` | API key wrong or billing exhausted |
| `relation "news" does not exist` | Schema SQL not yet executed |
| `permission denied for table news` | GRANT statements not executed, or wrong DB user |

---

## Maintenance

**What can break (and how to fix it):**
- HTML source layout changes → update CSS selector in `sources.py` (~5 min)
- Anthropic API credit runs out → top up at console.anthropic.com
- Supabase Free Tier storage limit → only relevant at ~500,000 articles (very long-term concern)

**Recommended routine:**
- Rotate `scraper_bot` password every 6 months (update GitHub Secret accordingly)
- Check the Actions tab once a week — all green?

---

## License

Private project — not licensed for external use or redistribution.

---

*Built with Python · Claude AI · Supabase · GitHub Actions · Lovable*
