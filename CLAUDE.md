# RSS Feed Generator — Developer Guide

This repo generates RSS 2.0 feeds for newsletters and blogs that lack native feeds,
then serves them via GitHub Pages.

## Repository layout

```
.
├── scrapers/              # One Python module per site
│   ├── __init__.py
│   └── pointer.py         # Pointer newsletter (pointerio.beehiiv.com)
├── feeds/                 # Generated XML files (committed by CI)
│   └── pointer.xml
├── .github/workflows/
│   └── update-feeds.yml   # Scheduled GitHub Actions job
├── generate_feeds.py      # Discovers scrapers, writes feeds/
├── requirements.txt
└── CLAUDE.md              # This file
```

## Feed URLs (after enabling GitHub Pages)

| Site    | Feed URL                                                   |
|---------|------------------------------------------------------------|
| Pointer | `https://<your-username>.github.io/<repo>/feeds/pointer.xml` |

---

## How to add a new site

### 1. Create a scraper module

Copy `scrapers/pointer.py` as a starting point and save it as
`scrapers/<site-id>.py` where `<site-id>` is a short, lowercase, hyphen-free
identifier (e.g. `tldr`, `morningbrew`, `hackernewsletter`).

Every scraper **must** expose:

```python
SITE_CONFIG: dict          # Feed metadata
get_articles() -> list[dict]   # Returns article dicts
```

#### SITE_CONFIG keys

| Key           | Required | Description                                              |
|---------------|----------|----------------------------------------------------------|
| `id`          | yes      | Unique identifier; determines the output filename        |
| `title`       | yes      | Feed title shown in RSS readers                          |
| `description` | yes      | Short description of the newsletter                      |
| `link`        | yes      | Homepage URL of the newsletter                           |
| `language`    | no       | BCP-47 language tag (default `"en"`)                     |
| `max_items`   | no       | Maximum items to include (default should be ≤ 20)        |
| `schedule`    | no       | Cron string for the publishing cadence (documentation)   |

#### Article dict keys returned by get_articles()

| Key        | Type       | Description                              |
|------------|------------|------------------------------------------|
| `title`    | `str`      | Article/issue title                      |
| `url`      | `str`      | Canonical URL for this article           |
| `pub_date` | `datetime` | Publish date (timezone-aware preferred)  |
| `content`  | `str`      | Full HTML body of the article            |

### 2. Implement _fetch_post_urls() and _fetch_post()

- `_fetch_post_urls()` — load the site's archive/listing page and return a list
  of post URLs. Use `requests` + `BeautifulSoup`.  Deduplicate with a `set`.

- `_fetch_post()` — given a URL, return the article dict above.
  Include a `time.sleep(1.5)` between sequential fetches to be polite.

#### Typical BeautifulSoup content selectors (try in order)

```python
candidates = [
    soup.find("div", attrs={"data-testid": re.compile(r"post|content")}),
    soup.find("div", class_=re.compile(r"post-content|content-body")),
    soup.find("div", class_=re.compile(r"\bprose\b")),
    soup.find("article"),
    soup.find("main"),
]
content_node = next((c for c in candidates if c), None)
```

### 3. Update the GitHub Actions schedule

Open `.github/workflows/update-feeds.yml` and add a `cron` entry that matches
the new site's publishing cadence:

```yaml
on:
  schedule:
    - cron: "0 11 * * 1"   # Monday   (Pointer)
    - cron: "0 11 * * 4"   # Thursday (Pointer)
    - cron: "0 8  * * 2"   # Tuesday  (new site, example)
```

If the new site publishes daily, a single `"0 8 * * *"` entry is fine.

### 4. Test locally

```bash
pip install -r requirements.txt
python generate_feeds.py
# Inspect feeds/<site-id>.xml
```

### 5. Commit and push

```bash
git add scrapers/<site-id>.py .github/workflows/update-feeds.yml
git commit -m "feat: add <site-name> RSS feed"
git push
```

The next scheduled (or manually triggered) Actions run will populate
`feeds/<site-id>.xml` and commit it.

---

## First-time GitHub Pages setup

1. Go to **Settings → Pages** in your repository.
2. Under **Source**, select **Deploy from a branch**.
3. Choose **Branch: `main`** and **Folder: `/ (root)`**.
4. Save. GitHub will publish the site at
   `https://<username>.github.io/<repo>/`.
5. Set the `GITHUB_PAGES_BASE` variable (Settings → Secrets and variables →
   Actions → Variables) to that URL, e.g.
   `https://yourusername.github.io/rssfeeds`
   This lets the workflow embed the correct self-link in each feed.

## Running the workflow manually

After pushing your changes, go to **Actions → Update RSS Feeds → Run workflow**
to trigger an immediate run without waiting for the next scheduled execution.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Content div is empty | Open the post URL in a browser, inspect the DOM, and find the actual class name; update the selector in the scraper |
| Dates parse as "now" | Find the date element via browser DevTools and update `_parse_date()` |
| Feed not updating | Check the Actions log; ensure the repo has write permissions (`Settings → Actions → General → Workflow permissions → Read and write`) |
| XML validation error | Run `xmllint --noout feeds/<id>.xml` locally to pinpoint the issue |
