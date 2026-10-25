#!/usr/bin/env python3
"""Fetch Janes Auctions past auction listings from the HiBid past-auctions page and generate a grouped Past Sales archive page."""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import requests
from bs4 import BeautifulSoup

PAST_URL = "https://janesauctions.hibid.com/auctions/past"
REPO_ROOT = Path(__file__).resolve().parent.parent
ARCHIVED_JSON = REPO_ROOT / "archived-auctions.json"
PAST_SALES_HTML = REPO_ROOT / "past-sales.html"

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

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def ensure_data_file():
    if not ARCHIVED_JSON.exists():
        ARCHIVED_JSON.write_text(json.dumps([], indent=2) + "\n")


def fetch_past_auctions():
    resp = requests.get(PAST_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    auctions = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not re.search(r"/(auction|catalog)/\d+", href):
            continue
        title = a.get_text(" ", strip=True)
        if not title:
            continue
        full_url = href if href.startswith("http") else f"https://janesauctions.hibid.com{href}"
        auction_id_match = re.search(r"/(?:auction|catalog)/(\d+)", href)
        auction_id = auction_id_match.group(1) if auction_id_match else full_url
        if auction_id in seen:
            continue
        seen.add(auction_id)
        auctions.append({"id": auction_id, "title": title, "url": full_url})

    return auctions


def parse_year_month(item):
    text = " ".join((str(item.get("title") or ""), str(item.get("url") or ""))).lower()
    month_lookup = {
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    }
    year_match = re.search(r"\b(19\d{2}|20\d{2})\b", text)
    year = int(year_match.group(1)) if year_match else 0
    month = 0
    for name, value in month_lookup.items():
        if name in text:
            month = value
            break
    return year, month


def sort_past_sales(raw):
    def key(item):
        year, month = parse_year_month(item)
        return (year, month)
    return sorted(raw, key=key, reverse=True)


def group_by_year_and_month(items):
    grouped = defaultdict(lambda: defaultdict(list))
    for item in sort_past_sales(items):
        year, month = parse_year_month(item)
        if year == 0:
            year = "Unknown"
        grouped[year][month].append(item)

    ordered_years = []
    for year in sorted(grouped.keys(), key=lambda y: (y == "Unknown", -(y if isinstance(y, int) else 0)), reverse=True):
        ordered_months = []
        for month in sorted(grouped[year].keys(), key=lambda m: (m == 0, -(m if isinstance(m, int) else 0)), reverse=True):
            ordered_months.append({
                "month": month,
                "label": MONTHS.get(month, "Unknown"),
                "items": grouped[year][month],
            })
        ordered_years.append({"year": year, "months": ordered_months})

    return ordered_years


def write_past_sales_page(items):
    groups = group_by_year_and_month(items)
    sections = []
    if not groups:
        sections.append("    <p class=\"empty\">No past sales yet. Check back soon.</p>")
    else:
        for year_group in groups:
            year_label = str(year_group["year"]) if year_group["year"] != "Unknown" else "Unknown"
            sections.append("    <section class=\"year-block\">")
            sections.append(f"      <h2 class=\"year-title\">{year_label}</h2>")
            for month_group in year_group["months"]:
                label = MONTHS.get(month_group["month"], "Unknown") if month_group["month"] else "Unknown"
                sections.append("      <div class=\"month-block\">")
                sections.append(f"        <h3 class=\"month-title\">{label}</h3>")
                sections.append("        <ul class=\"auction-list\">")
                for item in month_group["items"]:
                    title = item.get("title") or "Untitled auction"
                    url = item.get("url") or "#"
                    sections.append(f"          <li><a href=\"{url}\" target=\"_blank\" rel=\"noopener\">{title}</a></li>")
                sections.append("        </ul>")
                sections.append("      </div>")
            sections.append("    </section>")

    html_doc = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"UTF-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>Past Sales | Janes Auctions LLC</title>
  <meta name=\"description\" content=\"Browse archived Janes Auctions listings by year and month.\" />
  <style>
    :root {{ --bg:#FAFAF8; --ink:#1C1C1A; --muted:#6B7280; --rule:#E4E2DC; --accent:#C94000; --max:1120px; --pad:clamp(1.5rem, 5vw, 4rem); }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; font-family: Arial, sans-serif; background: var(--bg); color: var(--ink); line-height:1.6; }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .topbar {{ border-bottom:1px solid var(--rule); background:rgba(250,250,248,0.96); position:sticky; top:0; z-index:5; }}
    .inner {{ max-width: var(--max); margin:0 auto; padding:0 var(--pad); }}
    .nav {{ min-height:88px; display:flex; align-items:center; justify-content:space-between; gap:1rem; }}
    .brand {{ font-weight:700; letter-spacing:0.14em; text-transform:uppercase; color:var(--ink); }}
    .nav-links {{ list-style:none; display:flex; flex-wrap:wrap; gap:1.25rem; }}
    .nav-links a {{ font-size:0.75rem; letter-spacing:0.12em; text-transform:uppercase; color:var(--muted); }}
    .nav-links a:hover {{ color: var(--ink); }}
    .page {{ max-width: var(--max); margin:0 auto; padding: clamp(3rem, 8vw, 6rem) var(--pad); }}
    .eyebrow {{ color: var(--accent); font-size:0.72rem; letter-spacing:0.18em; text-transform:uppercase; font-weight:700; display:block; margin-bottom:1rem; }}
    h1 {{ font-size: clamp(2.6rem, 6vw, 4rem); line-height:1.1; margin-bottom:1rem; }}
    .subtitle {{ color: var(--muted); margin-bottom:2.5rem; max-width:60ch; }}
    .year-block {{ padding-bottom:1.5rem; margin-bottom:2rem; border-bottom:1px solid var(--rule); }}
    .year-title {{ font-size: clamp(1.8rem, 3vw, 2.5rem); margin-bottom:1rem; }}
    .month-block {{ margin-bottom:1.25rem; }}
    .month-title {{ font-size:0.9rem; letter-spacing:0.12em; text-transform:uppercase; color:var(--muted); margin-bottom:0.75rem; }}
    .auction-list {{ list-style:none; display:flex; flex-direction:column; gap:0.45rem; }}
    .auction-list li {{ padding-left:1rem; position:relative; }}
    .auction-list li::before {{ content:"—"; position:absolute; left:0; color:var(--accent); }}
    .empty {{ color: var(--muted); font-style: italic; }}
    footer {{ border-top:1px solid var(--rule); padding:2rem var(--pad); }}
    .footer-inner {{ max-width: var(--max); margin:0 auto; display:flex; justify-content:space-between; gap:1rem; flex-wrap:wrap; color:var(--muted); }}
    @media (max-width: 640px) {{ .nav {{ align-items:flex-start; flex-direction:column; padding:1rem 0; }} .nav-links {{ gap:0.85rem 1rem; }} }}
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

    {"\n".join(sections)}
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
    PAST_SALES_HTML.write_text(html_doc + "\n")
    print(f"Updated {PAST_SALES_HTML.name} with {len(items)} archived auctions")


def main():
    ensure_data_file()
    try:
        items = fetch_past_auctions()
    except Exception as exc:
        print(f"Error fetching past auctions: {exc}", file=sys.stderr)
        sys.exit(1)

    existing = []
    if ARCHIVED_JSON.exists():
        try:
            existing = json.loads(ARCHIVED_JSON.read_text())
        except json.JSONDecodeError:
            existing = []

    for item in items:
        if not any(a.get("id") == item.get("id") or a.get("url") == item.get("url") for a in existing):
            existing.append(item)

    existing = sorted(existing, key=lambda item: (item.get("id") or item.get("url")), reverse=True)
    ARCHIVED_JSON.write_text(json.dumps(existing, indent=2) + "\n")
    write_past_sales_page(existing)


if __name__ == "__main__":
    main()
