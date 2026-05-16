"""
Source configuration for the ImmoMenu News Scraper.

TWO SOURCE TYPES ARE SUPPORTED:

1. type: "rss"  → Parses an RSS/Atom feed (robust, preferred)
   Fields: name, type="rss", url

2. type: "html" → Scrapes an HTML listing page
   Fields: name, type="html", url, item_selector, base_url,
           article_selector (optional)

ADDING A NEW SOURCE:
1. Add an entry to SOURCES below
2. For HTML: find the right selector
   - Browser → open the source page → right-click a headline → "Inspect"
   - Identify which CSS selector matches the article link elements
3. Commit → picked up automatically on next scheduled run
"""

SOURCES = [
    # --- Source 1: Association press releases (HTML scraping) ---
    {
        "name": "Source Name – Press Releases",
        "type": "html",
        "url": "https://[REDACTED]/press-releases",
        "item_selector": "h3 a",
        "base_url": "https://[REDACTED]",
        "article_selector": None,
    },
    # --- Source 2: Association consultation responses (HTML scraping) ---
    {
        "name": "Source Name – Consultations",
        "type": "html",
        "url": "https://[REDACTED]/consultations",
        "item_selector": "h3 a",
        "base_url": "https://[REDACTED]",
        "article_selector": None,
    },
    # --- Source 3: National broadcaster economy section (RSS) ---
    {
        "name": "Swiss Broadcaster – Economy",
        "type": "rss",
        "url": "https://[REDACTED]/rss/economy",
    },

    # --- ADDITIONAL SOURCES: uncomment to activate ---
    #
    # {
    #     "name": "Source Name – Category",
    #     "type": "html",
    #     "url": "https://[REDACTED]/category",
    #     "item_selector": "h3 a",
    #     "base_url": "https://[REDACTED]",
    # },
    #
    # {
    #     "name": "Source Name – RSS",
    #     "type": "rss",
    #     "url": "https://[REDACTED]/feed.xml",
    # },
]

# Maximum items fetched per source per run
# (prevents a large first-run from triggering hundreds of Claude API calls)
MAX_ITEMS_PER_SOURCE = 15

# Minimum relevance score for an item to be written to the database.
# Scale: 1–10. 5 = borderline, 6 = relevant, 7+ = highly relevant.
MIN_RELEVANCE_SCORE = 6

# Claude model to use for enrichment.
# claude-opus-4-7 = highest quality
# claude-haiku-4-5 = lower cost alternative
CLAUDE_MODEL = "claude-opus-4-7"

# Controlled tag vocabulary. Claude is instructed to select only from this list.
# Ensures consistent filtering and reliable frontend tag buttons.
ALLOWED_TAGS = [
    "eigenmietwert",
    "mietrecht",
    "steuern",
    "marktpreise",
    "bauen",
    "sanieren",
    "energie",
    "hypotheken",
    "recht",
    "verkauf",
    "kauf",
    "politik",
    "stockwerkeigentum",
    "grundstueckgewinnsteuer",
    "erbrecht",
    "wohneigentum",
    "vermieten",
]
