"""
Scraper for Pointer (https://pointerio.beehiiv.com/)
Essential Reading For Engineering Leaders — publishes Monday & Thursday.
"""
import re
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

SITE_CONFIG = {
    "id": "pointer",
    "title": "Pointer",
    "description": "Essential Reading For Engineering Leaders",
    "link": "https://pointerio.beehiiv.com/",
    "language": "en",
    "max_items": 10,
    # Pointer publishes Monday and Thursday; run at 10:00 UTC to catch morning issues
    "schedule": "0 10 * * 1,4",
}

BASE_URL = "https://pointerio.beehiiv.com"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def _get(url: str) -> requests.Response:
    resp = requests.get(url, headers=_HEADERS, timeout=30)
    resp.raise_for_status()
    return resp


def _fetch_post_urls() -> list[str]:
    """Scrape the listing page and return up to max_items post URLs."""
    soup = BeautifulSoup(_get(BASE_URL + "/").text, "lxml")

    seen: set[str] = set()
    urls: list[str] = []

    for a in soup.find_all("a", href=re.compile(r"^/p/[a-z0-9-]+$")):
        url = BASE_URL + a["href"]
        if url not in seen:
            seen.add(url)
            urls.append(url)

    return urls[: SITE_CONFIG["max_items"]]


def _parse_date(soup: BeautifulSoup) -> datetime:
    """Extract publish date from JSON-LD structured data (beehiiv standard)."""
    import json

    for script in soup.find_all("script", type="application/ld+json"):
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
            for key in ("datePublished", "dateModified"):
                raw = data.get(key)
                if raw:
                    return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except (ValueError, KeyError):
            pass

    # Fallback: <time datetime="…">
    time_el = soup.find("time")
    if time_el:
        dt_str = time_el.get("datetime", "")
        if dt_str:
            try:
                return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            except ValueError:
                pass

    return datetime.now(timezone.utc)


def _extract_content(soup: BeautifulSoup, url: str) -> str:
    """
    Extract the main HTML content from a beehiiv post page.

    Beehiiv SSR pages render content into a <div> whose class varies by
    theme/version. We try several selectors in priority order.
    """
    candidates = [
        # Beehiiv's rendered post container (confirmed working as of 2026-02)
        soup.find("div", class_="rendered-post"),
        # Newer beehiiv builds
        soup.find("div", attrs={"data-testid": re.compile(r"post-content|email")}),
        # Common class fragments
        soup.find("div", class_=re.compile(r"post-content|content-body|email-content")),
        # Generic prose container (Tailwind)
        soup.find("div", class_=re.compile(r"\bprose\b")),
        # Fallback: outermost article
        soup.find("article"),
        # Last resort: main element
        soup.find("main"),
    ]

    for node in candidates:
        if node:
            # Strip script/style children to keep feed content clean
            for tag in node.find_all(["script", "style", "noscript"]):
                tag.decompose()
            return str(node)

    return f'<p>Read the full issue at <a href="{url}">{url}</a></p>'


def _fetch_post(url: str) -> dict:
    """Fetch a single newsletter post and return a normalised article dict."""
    soup = BeautifulSoup(_get(url).text, "lxml")

    # Title
    h1 = soup.find("h1")
    title = h1.get_text(strip=True) if h1 else url.split("/p/")[-1].replace("-", " ").title()

    return {
        "title": title,
        "url": url,
        "pub_date": _parse_date(soup),
        "content": _extract_content(soup, url),
    }


def get_articles() -> list[dict]:
    """Entry point called by generate_feeds.py — returns list of article dicts."""
    urls = _fetch_post_urls()
    articles: list[dict] = []

    for i, url in enumerate(urls):
        if i > 0:
            time.sleep(1.5)  # polite crawl delay
        try:
            article = _fetch_post(url)
            articles.append(article)
            print(f"    fetched: {article['title'][:60]}")
        except Exception as exc:
            print(f"    failed {url}: {exc}")

    return articles
