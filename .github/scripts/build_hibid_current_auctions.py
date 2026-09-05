#!/usr/bin/env python3
"""
Fetch HiBid company page(s), extract auction links, and write current-auctions.html.
Set HIBID_URLS as a comma-separated env var (or the script falls back to a default).
Optionally set HIBID_VIEW_LINK for the big button. This script is intentionally
robust: it uses heuristics to locate auction links. Edit the selectors if HiBid markup changes.
"""
import os
import sys
import re
import datetime
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

DEFAULT_HIBID = "https://hibid.com/company/150802/janes-auctions"
# If you prefer the other company id for the View button, set HIBID_VIEW_LINK secret to that URL:
# e.g. https://hibid.com/company/101690/janes-auctions-llc

def fetch(url):
    headers = {"User-Agent": "janesauctions-github-action/1.0 (+https://github.com/JanesAuctions/janesauctions.com)"}
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.text

def find_auction_links(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    anchors = soup.find_all("a", href=True)

    candidates = []
    for a in anchors:
        href = a["href"].strip()
        text = a.get_text(" ", strip=True)
        # Heuristic: href that looks like an auction or lot path
        if re.search(r"/auction\b|/auctions\b|/lot\b|/lotInfo\b|/items\b|/sale\b", href, re.I):
            full = urljoin(base_url, href)
            title = text or full
            candidates.append((full, title))
    # Fallback: sometimes auctions are provided as links with data attributes or in a listing section
    if not candidates:
        # search for elements that look like listing rows
        listings = soup.find_all(class_=re.compile(r"auction|listing|sale", re.I))
        for item in listings:
            a = item.find("a", href=True)
            if a:
                href = a["href"].strip()
                full = urljoin(base_url, href)
                title = a.get_text(" ", strip=True) or full
                candidates.append((full, title))

    # Deduplicate while preserving order
    seen = set()
    out = []
    for href, title in candidates:
        if href not in seen:
            seen.add(href)
            out.append((href, title))
    return out

def build_html(all_auctions, view_link):
    now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    parts = []
    parts.append("<!doctype html>")
    parts.append("<html><head><meta charset='utf-8'><title>Current Auctions</title>")
    parts.append("<meta name='viewport' content='width=device-width,initial-scale=1'/>")
    parts.append("<style>body{font-family:Arial,Helvetica,sans-serif;padding:1rem} .btn{display:inline-block;padding:.5rem .75rem;background:#007bff;color:#fff;border-radius:.25rem;text-decoration:none} ul{padding-left:1.2rem}</style>")
    parts.append("</head><body>")
    parts.append("<h1>Current Auctions</h1>")
    parts.append(f"<p>Updated: {now}</p>")

    parts.append(f'<p><a class="btn" href="{view_link}" target="_blank" rel="noopener">View Current Auctions</a></p>')

    if not all_auctions:
        parts.append("<p>No individual auction links could be detected on the HiBid page. Click the button above to view current auctions on HiBid.</p>")
    else:
        parts.append("<ul>")
        for href, title in all_auctions:
            safe_title = title.replace("<", "&lt;").replace(">", "&gt;")
            parts.append(f'<li><a href="{href}" target="_blank" rel="noopener">{safe_title}</a></li>')
        parts.append("</ul>")

    parts.append("<hr><p>Automated update via GitHub Action.</p>")
    parts.append("</body></html>")
    return "\n".join(parts)

def main():
    env_urls = os.getenv("HIBID_URLS", "").strip()
    if env_urls:
        urls = [u.strip() for u in env_urls.split(",") if u.strip()]
    else:
        urls = [DEFAULT_HIBID]

    view_link = os.getenv("HIBID_VIEW_LINK", "").strip() or urls[0]

    all_auctions = []
    seen = set()
    for url in urls:
        try:
            html = fetch(url)
        except Exception as e:
            print(f"Failed to fetch {url}: {e}", file=sys.stderr)
            continue
        links = find_auction_links(html, url)
        for href, title in links:
            if href not in seen:
                all_auctions.append((href, title))
                seen.add(href)

    out = build_html(all_auctions, view_link)
    target = "current-auctions.html"
    # Only write if content changed to avoid unnecessary commits
    if os.path.exists(target):
        with open(target, "r", encoding="utf-8") as f:
            old = f.read()
        if old == out:
            print("No change to current-auctions.html")
            return
    with open(target, "w", encoding="utf-8") as f:
        f.write(out)
    print(f"Wrote {target} with {len(all_auctions)} detected auction(s).")

if __name__ == "__main__":
    main()
