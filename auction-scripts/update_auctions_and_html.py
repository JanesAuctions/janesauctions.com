#!/usr/bin/env python3
"""
Scrapes HiBid auctions and updates both auctions.json and index.html.
Automatically moves expired auctions to the archived sales section.
"""
import json
import re
import sys
import html
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HIBID_URL = "https://hibid.com/company/150802/janes-auctions"
REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_JSON = REPO_ROOT / "auctions.json"
ARCHIVED_JSON = REPO_ROOT / "archived-auctions.json"
INDEX_HTML = REPO_ROOT / "index.html"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def fetch_auctions():
    """Fetch auctions from HiBid"""
    resp = requests.get(HIBID_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    auctions = []
    seen_ids = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.search(r"/(auction|catalog)/\d+/", href):
            title = a.get_text(strip=True)
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
    """Load archived auctions from JSON file"""
    if ARCHIVED_JSON.exists():
        return json.loads(ARCHIVED_JSON.read_text())
    return []


def save_archived(archived):
    """Save archived auctions to JSON file"""
    ARCHIVED_JSON.write_text(json.dumps(archived, indent=2) + "\n")


def deduplicate_archived(archived):
    """Remove duplicates from archived list by ID"""
    seen = set()
    deduped = []
    for item in archived:
        item_id = item.get("id") or item.get("url")
        if item_id not in seen:
            seen.add(item_id)
            deduped.append(item)
    return deduped


def generate_auction_list_html(auctions):
    """Generate HTML list items for auctions"""
    if not auctions:
        return "          <li><em>No active auctions at this time. Check back soon!</em></li>"
    
    items = []
    for auction in auctions:
        title = html.escape(auction["title"])
        url = html.escape(auction["url"])
        items.append(
            f'          <li><a href="{url}" target="_blank" rel="noopener">{title}</a></li>'
        )
    return "\n".join(items)


def generate_archived_list_html(archived):
    """Generate HTML list items for archived auctions"""
    if not archived:
        return ""
    
    items = []
    for auction in archived:
        title = html.escape(auction["title"])
        url = html.escape(auction["url"])
        items.append(
            f'      <li><a href="{url}" target="_blank" rel="noopener">{title}</a></li>'
        )
    return "\n".join(items)


def update_index_html(auctions, archived):
    """Update both current and archived auction lists in index.html"""
    html_content = INDEX_HTML.read_text()
    
    # Update current auctions list
    current_list_html = generate_auction_list_html(auctions)
    pattern_current = r'(<ul class="current-auctions-list">).*?(</ul>)'
    replacement_current = f'\\1\n{current_list_html}\n        \\2'
    updated_html = re.sub(pattern_current, replacement_current, html_content, flags=re.DOTALL)
    
    # Update archived auctions list
    archived_list_html = generate_archived_list_html(archived)
    if archived_list_html:
        pattern_archived = r'(<ul class="archived-sales-list" id="archived-list">).*?(</ul>)'
        replacement_archived = f'\\1\n{archived_list_html}\n    \\2'
        updated_html = re.sub(pattern_archived, replacement_archived, updated_html, flags=re.DOTALL)
    
    # Write back
    INDEX_HTML.write_text(updated_html)
    print(f"Updated index.html with {len(auctions)} active and {len(archived)} archived auction(s)")


def main():
    try:
        current_auctions = fetch_auctions()
    except Exception as e:
        print(f"Error fetching auctions: {e}", file=sys.stderr)
        sys.exit(1)

    # Load previous auctions and archived list
    try:
        previous_auctions = json.loads(OUTPUT_JSON.read_text()) if OUTPUT_JSON.exists() else []
    except Exception as e:
        print(f"Warning: Could not load previous auctions: {e}", file=sys.stderr)
        previous_auctions = []
    
    archived = load_archived()
    
    # Find expired auctions (were in previous but not in current)
    current_ids = {a.get("id") or a.get("url") for a in current_auctions}
    previous_ids = {a.get("id") or a.get("url") for a in previous_auctions}
    
    expired_ids = previous_ids - current_ids
    
    # Move expired auctions to archive
    for prev_auction in previous_auctions:
        prev_id = prev_auction.get("id") or prev_auction.get("url")
        if prev_id in expired_ids:
            # Check if already in archive to avoid duplicates
            if not any(a.get("id") == prev_id or a.get("url") == prev_auction.get("url") 
                      for a in archived):
                archived.append(prev_auction)
                print(f"Archived: {prev_auction['title']}")
    
    # Deduplicate archived list
    archived = deduplicate_archived(archived)
    
    # Save to JSON files
    OUTPUT_JSON.write_text(json.dumps(current_auctions, indent=2) + "\n")
    print(f"Wrote {len(current_auctions)} auction(s) to {OUTPUT_JSON}")
    
    save_archived(archived)
    print(f"Wrote {len(archived)} archived auction(s) to {ARCHIVED_JSON}")
    
    # Update HTML
    try:
        update_index_html(current_auctions, archived)
    except Exception as e:
        print(f"Error updating HTML: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
