#!/usr/bin/env python3
"""
generate_feeds.py — discover all scrapers and write RSS 2.0 feeds to feeds/.

Each scraper in the scrapers/ package must expose:
    SITE_CONFIG : dict   — feed metadata (id, title, description, link, …)
    get_articles() -> list[dict]  — returns articles with keys:
                                    title, url, pub_date, content
"""
import importlib
import os
import pkgutil
from datetime import datetime, timezone
from email.utils import format_datetime

from lxml import etree

import scrapers

FEEDS_DIR = "feeds"

CONTENT_NS = "http://purl.org/rss/1.0/modules/content/"
ATOM_NS = "http://www.w3.org/2005/Atom"
DC_NS = "http://purl.org/dc/elements/1.1/"


def _rfc822(dt: datetime) -> str:
    """Format a datetime as RFC 822 (required by RSS 2.0 pubDate)."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return format_datetime(dt)


def _plain_text(html: str, max_chars: int = 400) -> str:
    """Strip HTML tags for the <description> fallback."""
    from bs4 import BeautifulSoup

    text = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
    return text[:max_chars].rsplit(" ", 1)[0] + "…" if len(text) > max_chars else text


def _feed_url(config: dict) -> str:
    """Return the public GitHub Pages URL for a feed, if configured."""
    pages_base = os.environ.get("GITHUB_PAGES_BASE", "").rstrip("/")
    if pages_base:
        return f"{pages_base}/feeds/{config['id']}.xml"
    return ""


def generate_rss(config: dict, articles: list[dict]) -> bytes:
    """Produce an RSS 2.0 document with content:encoded for full HTML bodies."""
    nsmap = {
        "atom": ATOM_NS,
        "content": CONTENT_NS,
        "dc": DC_NS,
    }

    rss = etree.Element("rss", nsmap=nsmap)
    rss.set("version", "2.0")

    channel = etree.SubElement(rss, "channel")
    etree.SubElement(channel, "title").text = config["title"]
    etree.SubElement(channel, "link").text = config["link"]
    etree.SubElement(channel, "description").text = config["description"]
    etree.SubElement(channel, "language").text = config.get("language", "en")
    etree.SubElement(channel, "lastBuildDate").text = _rfc822(datetime.now(timezone.utc))
    etree.SubElement(channel, "ttl").text = "360"  # suggest refresh every 6 hours

    # Atom self-link (good practice; helps feed validators)
    feed_url = _feed_url(config)
    if feed_url:
        atom_link = etree.SubElement(channel, f"{{{ATOM_NS}}}link")
        atom_link.set("href", feed_url)
        atom_link.set("rel", "self")
        atom_link.set("type", "application/rss+xml")

    for article in articles:
        item = etree.SubElement(channel, "item")
        etree.SubElement(item, "title").text = article["title"]
        etree.SubElement(item, "link").text = article["url"]
        etree.SubElement(item, "guid", isPermaLink="true").text = article["url"]
        etree.SubElement(item, "pubDate").text = _rfc822(article["pub_date"])

        content_html = article.get("content", "")

        # Full HTML content — most modern readers (Reeder, NetNewsWire, …) display this
        content_el = etree.SubElement(item, f"{{{CONTENT_NS}}}encoded")
        content_el.text = etree.CDATA(content_html)

        # Plain-text description as fallback for simpler readers
        etree.SubElement(item, "description").text = _plain_text(content_html)

    return etree.tostring(
        rss, pretty_print=True, xml_declaration=True, encoding="UTF-8"
    )


def generate_index_html(configs: list[dict]) -> None:
    """Write index.html to the repo root listing all feeds."""
    pages_base = os.environ.get("GITHUB_PAGES_BASE", "").rstrip("/")
    built_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    feed_items = ""
    for cfg in configs:
        feed_url = f"{pages_base}/feeds/{cfg['id']}.xml" if pages_base else f"feeds/{cfg['id']}.xml"
        feed_items += f"""
        <li class="feed-card">
          <div class="feed-header">
            <svg class="rss-icon" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
              <circle cx="5" cy="19" r="2"/>
              <path d="M4 4a16 16 0 0 1 16 16" stroke-width="2" stroke-linecap="round"/>
              <path d="M4 11a9 9 0 0 1 9 9" stroke-width="2" stroke-linecap="round"/>
            </svg>
            <h2><a href="{cfg['link']}" target="_blank" rel="noopener">{cfg['title']}</a></h2>
          </div>
          <p class="feed-desc">{cfg['description']}</p>
          <a class="feed-link" href="{feed_url}">
            Subscribe to RSS feed &rarr;
          </a>
        </li>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>RSS Feeds</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    :root {{
      --bg: #0f1117;
      --surface: #1a1d27;
      --border: #2a2d3a;
      --text: #e2e4ed;
      --muted: #7b7f96;
      --accent: #f26522;
      --accent-hover: #ff7a36;
      --radius: 10px;
    }}

    body {{
      background: var(--bg);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      line-height: 1.6;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }}

    header {{
      padding: 3rem 1.5rem 2rem;
      max-width: 680px;
      margin: 0 auto;
      width: 100%;
    }}

    header h1 {{
      font-size: 2rem;
      font-weight: 700;
      letter-spacing: -0.02em;
      color: var(--text);
    }}

    header p {{
      margin-top: 0.5rem;
      color: var(--muted);
      font-size: 1rem;
    }}

    main {{
      flex: 1;
      max-width: 680px;
      margin: 0 auto;
      width: 100%;
      padding: 0 1.5rem 3rem;
    }}

    ul {{
      list-style: none;
      display: flex;
      flex-direction: column;
      gap: 1rem;
    }}

    .feed-card {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 1.25rem 1.5rem;
      transition: border-color 0.15s;
    }}

    .feed-card:hover {{
      border-color: var(--accent);
    }}

    .feed-header {{
      display: flex;
      align-items: center;
      gap: 0.6rem;
      margin-bottom: 0.4rem;
    }}

    .rss-icon {{
      width: 20px;
      height: 20px;
      flex-shrink: 0;
      stroke: var(--accent);
    }}

    .feed-header h2 {{
      font-size: 1.1rem;
      font-weight: 600;
    }}

    .feed-header h2 a {{
      color: var(--text);
      text-decoration: none;
    }}

    .feed-header h2 a:hover {{
      color: var(--accent);
    }}

    .feed-desc {{
      color: var(--muted);
      font-size: 0.9rem;
      margin-bottom: 0.85rem;
    }}

    .feed-link {{
      display: inline-block;
      font-size: 0.85rem;
      font-weight: 500;
      color: var(--accent);
      text-decoration: none;
      border: 1px solid var(--accent);
      border-radius: 6px;
      padding: 0.3rem 0.75rem;
      transition: background 0.15s, color 0.15s;
    }}

    .feed-link:hover {{
      background: var(--accent);
      color: #fff;
    }}

    footer {{
      text-align: center;
      padding: 1.5rem;
      color: var(--muted);
      font-size: 0.8rem;
      border-top: 1px solid var(--border);
    }}

    footer a {{
      color: var(--muted);
    }}
  </style>
</head>
<body>
  <header>
    <h1>RSS Feeds</h1>
    <p>Custom feeds for newsletters that don&#8217;t provide one natively.</p>
  </header>
  <main>
    <ul>{feed_items}
    </ul>
  </main>
  <footer>
    <p>Updated {built_at} &middot; <a href="https://github.com/jiawenpan/rssfeeds">Source on GitHub</a></p>
  </footer>
</body>
</html>
"""

    with open("index.html", "w", encoding="utf-8") as fh:
        fh.write(html)
    print("  wrote index.html")


def main() -> None:
    os.makedirs(FEEDS_DIR, exist_ok=True)

    found = 0
    all_configs: list[dict] = []

    for _, module_name, _ in pkgutil.iter_modules(scrapers.__path__):
        if module_name.startswith("_"):
            continue

        module = importlib.import_module(f"scrapers.{module_name}")

        if not hasattr(module, "SITE_CONFIG") or not hasattr(module, "get_articles"):
            print(f"[skip] {module_name}: missing SITE_CONFIG or get_articles()")
            continue

        config = module.SITE_CONFIG
        print(f"\n[{config['id']}] {config['title']}")

        try:
            articles = module.get_articles()
            if not articles:
                print("  no articles returned — skipping write")
                continue

            xml_bytes = generate_rss(config, articles)
            out_path = os.path.join(FEEDS_DIR, f"{config['id']}.xml")
            with open(out_path, "wb") as fh:
                fh.write(xml_bytes)

            print(f"  wrote {len(articles)} items → {out_path}")
            found += 1
            all_configs.append(config)
        except Exception as exc:  # noqa: BLE001
            import traceback

            print(f"  ERROR: {exc}")
            traceback.print_exc()

    print(f"\nDone — {found} feed(s) updated.")
    print("\n[index]")
    generate_index_html(all_configs)


if __name__ == "__main__":
    main()
