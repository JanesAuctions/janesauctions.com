#!/usr/bin/env python3
"""
Scrapes HiBid auctions and updates active auctions, archive JSON, and a Past Sales page.
"""
import html
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HIBID_URL = "https://hibid.com/company/150802/janes-auctions"
PAST_SALES_URL = "https://janesauctions.hibid.com/auctions/past"
REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_JSON = REPO_ROOT / "auctions.json"
ARCHIVED_JSON = REPO_ROOT / "archived-auctions.json"
INDEX_HTML = REPO_ROOT / "index.html"
PAST_SALES_HTML = REPO_ROOT / "past-sales.html"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

MONTHS = {
    1: "January",
    2: "February",
    3: "March",
    4: "April",
    5: "May",
    6: "June",
    7: "July",
    8: "August",
    9: "September",
    10: "October",
    11: "November",
    12: "December",
}


def ensure_archived_file_exists():
    if not ARCHIVED_JSON.exists():
        ARCHIVED_JSON.write_text(json.dumps([], indent=2) + "\n")


def fetch_auctions():
    resp = requests.get(HIBID_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    auctions = []
    seen_ids = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.search(r"/(auction|catalog)/\d+/", href):
            title = a.get_text(" ", strip=True)
            if not title:
                continue
            full_url = href if href.startswith("http") else f"https://hibid.com{href}"
            auction_id_match = re.search(r"/(?:auction|catalog)/(\d+)/", href)
            auction_id = auction_id_match.group(1) if auction_id_match else full_url
            if auction_id in seen_ids:
                continue
            seen_ids.add(auction_id)
            auctions.append({"id": auction_id, "title": title, "url": full_url})

    return auctions


def load_archived():
    ensure_archived_file_exists()
    if ARCHIVED_JSON.exists():
        try:
            return json.loads(ARCHIVED_JSON.read_text())
        except json.JSONDecodeError:
            return []
    return []


def save_archived(archived):
    ARCHIVED_JSON.write_text(json.dumps(archived, indent=2) + "\n")


def deduplicate_archived(archived):
    seen = set()
    deduped = []
    for item in archived:
        item_id = item.get("id") or item.get("url")
        if item_id not in seen:
            seen.add(item_id)
            deduped.append(item)
    return deduped


def parse_year_month(item):
    text = " ".join([
        str(item.get("title") or ""),
        str(item.get("url") or ""),
    ])
    lower = text.lower()

    month_names = {
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }
    month = None
    for name, value in month_names.items():
        if name in lower:
            month = value
            break

    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", text)
    year = int(year_match.group(1)) if year_match else 0
    if not month and year == 0:
        return 0, 0
    return year, month or 0


def sort_archived_for_display(archived):
    def score(item):
        year, month = parse_year_month(item)
        return (year, month)
    return sorted(archived, key=score, reverse=True)


def group_archived_by_year_month(archived):
    grouped = defaultdict(lambda: defaultdict(list))
    for item in sort_archived_for_display(archived):
        year, month = parse_year_month(item)
        if year == 0:
            year = "Unknown"
        grouped[year][month].append(item)

    ordered_years = []
    for year in sorted(grouped.keys(), key=lambda y: (y == "Unknown", -(y if isinstance(y, int) else 0)), reverse=True):
        months = sorted(grouped[year].keys(), key=lambda m: (m == 0, -(m if isinstance(m, int) else 0)), reverse=True)
        ordered_months = []
        for month in months:
            ordered_months.append({
                "month": month,
                "label": MONTHS.get(month, "Unknown"),
                "items": grouped[year][month],
            })
        ordered_years.append({"year": year, "months": ordered_months})

    return ordered_years


def generate_auction_list_html(auctions):
    if not auctions:
        return "          <li><em>No active auctions at this time. Check back soon!</em></li>"

    items = []
    for auction in auctions:
        title = html.escape(auction["title"])
        url = html.escape(auction["url"])
        items.append(f'          <li><a href="{url}" target="_blank" rel="noopener">{title}</a></li>')
    return "\n".join(items)


def generate_past_sales_html(archived):
    groups = group_archived_by_year_month(archived)
    sections = []
    if not groups:
        sections.append("    <p class=\"empty\">No past sales yet. Check back soon.</p>")
    else:
        for year_group in groups:
            year_value = year_group["year"]
            year_label = str(year_value) if year_value != "Unknown" else "Unknown"
            sections.append(f"    <section class=\"year-block\">")
            sections.append(f"      <h2 class=\"year-title\">{html.escape(year_label)}</h2>")
            for month_group in year_group["months"]:
                month_label = MONTHS.get(month_group["month"], "Unknown") if month_group["month"] else "Unknown"
                sections.append(f"      <div class=\"month-block\">")
                sections.append(f"        <h3 class=\"month-title\">{html.escape(month_label)}</h3>")
                sections.append("        <ul class=\"auction-list\">")
                for item in month_group["items"]:
                    title = html.escape(str(item.get("title") or "Untitled auction"))
                    url = html.escape(str(item.get("url") or "#"))
                    sections.append(f"          <li><a href=\"{url}\" target=\"_blank\" rel=\"noopener\">{title}</a></li>")
                sections.append("        </ul>")
                sections.append("      </div>")
            sections.append("    </section>")

    return """<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>Past Sales | Janes Auctions LLC</title>
  <meta name=\"description\" content=\"Browse archived Janes Auctions listings by year and month.\" />
  <style>
    :root { --bg:#FAFAF8; --ink:#1C1C1A; --muted:#6B7280; --rule:#E4E2DC; --accent:#C94000; --max:1120px; --pad:clamp(1.5rem, 5vw, 4rem); }
    * { box-sizing: border-box; }
    body { margin:0; font-family: Arial, sans-serif; background: var(--bg); color: var(--ink); line-height:1.6; }
    a { color: var(--accent); text-decoration: none; }
    a:hover { text-decoration: underline; }
    .topbar { border-bottom:1px solid var(--rule); background:rgba(250,250,248,0.94); position:sticky; top:0; z-index:5; }
    .inner { max-width: var(--max); margin:0 auto; padding:0 var(--pad); }
    .nav { min-height:88px; display:flex; align-items:center; justify-content:space-between; gap:1rem; }
    .brand { font-weight:700; letter-spacing:0.14em; text-transform:uppercase; color:var(--ink); }
    .nav-links { list-style:none; display:flex; flex-wrap:wrap; gap:1.25rem; }
    .nav-links a { font-size:0.75rem; letter-spacing:0.12em; text-transform:uppercase; color:var(--muted); }
    .nav-links a:hover { color: var(--ink); }
    .page { max-width: var(--max); margin:0 auto; padding: clamp(3rem, 8vw, 6rem) var(--pad); }
    .eyebrow { color: var(--accent); font-size:0.72rem; letter-spacing:0.18em; text-transform:uppercase; font-weight:700; display:block; margin-bottom:1rem; }
    h1 { font-size: clamp(2.6rem, 6vw, 4rem); line-height:1.1; margin-bottom:1rem; }
    .subtitle { color: var(--muted); margin-bottom:2.5rem; max-width:60ch; }
    .year-block { padding-bottom:1.5rem; margin-bottom:2rem; border-bottom:1px solid var(--rule); }
    .year-title { font-size: clamp(1.8rem, 3vw, 2.5rem); margin-bottom:1rem; }
    .month-block { margin-bottom: 1.25rem; }
    .month-title { font-size:0.9rem; letter-spacing:0.12em; text-transform:uppercase; color:var(--muted); margin-bottom:0.75rem; }
    .auction-list { list-style:none; display:flex; flex-direction:column; gap:0.45rem; }
    .auction-list li { padding-left:1rem; position:relative; }
    .auction-list li::before { content:"—"; position:absolute; left:0; color:var(--accent); }
    .empty { color: var(--muted); font-style: italic; }
    footer { border-top:1px solid var(--rule); padding:2rem var(--pad); }
    .footer-inner { max-width: var(--max); margin:0 auto; display:flex; justify-content:space-between; gap:1rem; flex-wrap:wrap; color:var(--muted); }
    @media (max-width: 640px) {
      .nav { align-items:flex-start; flex-direction:column; padding:1rem 0; }
      .nav-links { gap:0.85rem 1rem; }
    }
  </style>
</head>
<body>
  <header class=\"topbar\">
    <div class=\"inner nav\">
      <a class=\"brand\" href=\"index.html\">Janes Auctions</a>
      <ul class=\"nav-links\">
        <li><a href=\"index.html#about\">About</a></li>
        <li><a href=\"https://hibid.com/company/150802/janes-auctions\" target=\"_blank\" rel=\"noopener\">Auctions</a></li>
        <li><a href=\"index.html#consign\">Consign</a></li>
        <li><a href=\"past-sales.html\">Past Sales</a></li>
        <li><a href=\"index.html#contact\">Contact</a></li>
      </ul>
    </div>
  </header>

  <main class=\"page\">
    <span class=\"eyebrow\">Past Sales</span>
    <h1>Previous Auctions</h1>
    <p class=\"subtitle\">Links to auctions that are no longer active on HiBid. Newer sales appear first, grouped by year and month.</p>

    """ + "\n".join(sections) + """
  </main>

  <footer>
    <div class=\"footer-inner\">
      <span>© 2026 Janes Auctions LLC</span>
      <a href=\"https://hibid.com/company/150802/janes-auctions\" target=\"_blank\" rel=\"noopener\">Bid on HiBid.com →</a>
    </div>
  </footer>
</body>
</html>
"""


def update_index_html(auctions):
    html_content = INDEX_HTML.read_text()
    current_list_html = generate_auction_list_html(auctions)
    pattern_current = r'(<ul class="current-auctions-list">).*?(</ul>)'
    replacement_current = f'\\1\n{current_list_html}\n        \\2'
    updated_html = re.sub(pattern_current, replacement_current, html_content, flags=re.DOTALL)
    INDEX_HTML.write_text(updated_html)
    print(f"Updated index.html with {len(auctions)} active auction(s)")


def update_past_sales_html(archived):
    PAST_SALES_HTML.write_text(generate_past_sales_html(archived) + "\n")
    print(f"Updated past-sales.html with {len(archived)} archived auction(s)")


def main():
    ensure_archived_file_exists()

    try:
        current_auctions = fetch_auctions()
    except Exception as e:
        print(f"Error fetching auctions: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        previous_auctions = json.loads(OUTPUT_JSON.read_text()) if OUTPUT_JSON.exists() else []
    except Exception as e:
        print(f"Warning: Could not load previous auctions: {e}", file=sys.stderr)
        previous_auctions = []

    archived = load_archived()
    current_ids = {a.get("id") or a.get("url") for a in current_auctions}
    previous_ids = {a.get("id") or a.get("url") for a in previous_auctions}
    expired_ids = previous_ids - current_ids

    for prev_auction in previous_auctions:
        prev_id = prev_auction.get("id") or prev_auction.get("url")
        if prev_id in expired_ids and not any(a.get("id") == prev_id or a.get("url") == prev_auction.get("url") for a in archived):
            archived.append(prev_auction)
            print(f"Archived: {prev_auction['title']}")

    archived = deduplicate_archived(archived)
    OUTPUT_JSON.write_text(json.dumps(current_auctions, indent=2) + "\n")
    save_archived(archived)

    try:
        update_index_html(current_auctions)
    except Exception as e:
        print(f"Error updating index.html: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        update_past_sales_html(archived)
    except Exception as e:
        print(f"Error updating past-sales.html: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
