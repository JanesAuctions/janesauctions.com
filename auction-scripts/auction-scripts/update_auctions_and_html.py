#!/usr/bin/env python3
"""
Scrapes HiBid auctions and updates both auctions.json and index.html
"""
import json
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HIBID_URL = "https://hibid.com/company/150802/janes-auctions"
REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_JSON = REPO_ROOT / "auctions.json"
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
    seen_links = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.search(r"/(auction|catalog)/\d+/", href):
            title = a.get_text(strip=True)
            if not title:
                continue
            full_url = href if href.startswith("http") else f"https://hibid.com{href}"
            auction_id_match = re.search(r"/(?:auction|catalog)/(\d+)/", href)
            auction_id = auction_id_match.group(1) if auction_id_match else full_url

            if auction_id in seen_links:
                continue
            seen_links.add(auction_id)

            auctions.append({"title": title, "url": full_url})

    return auctions


def generate_auction_list_html(auctions):
    """Generate HTML list items for auctions"""
    if not auctions:
        return "          <li><em>No active auctions at this time. Check back soon!</em></li>"
    
    items = []
    for auction in auctions:
        items.append(
            f'          <li><a href="{auction["url"]}" target="_blank" rel="noopener">{auction["title"]}</a></li>'
        )
    return "\n".join(items)


def update_index_html(auctions):
    """Update the auction list in index.html"""
    html_content = INDEX_HTML.read_text()
    
    # Generate the new auction list HTML
    new_list = generate_auction_list_html(auctions)
    
    # Replace the auction list section
    # Find the current-auctions-list and replace its contents
    pattern = r'(<ul class="current-auctions-list">).*?(</ul>)'
    replacement = f'\\1\n{new_list}\n        \\2'
    
    updated_html = re.sub(pattern, replacement, html_content, flags=re.DOTALL)
    
    # Write back
    INDEX_HTML.write_text(updated_html)
    print(f"Updated index.html with {len(auctions)} auction(s)")


def main():
    try:
        auctions = fetch_auctions()
    except Exception as e:
        print(f"Error fetching auctions: {e}", file=sys.stderr)
        sys.exit(1)

    # Save to JSON
    OUTPUT_JSON.write_text(json.dumps(auctions, indent=2) + "\n")
    print(f"Wrote {len(auctions)} auction(s) to {OUTPUT_JSON}")
    
    # Update HTML
    try:
        update_index_html(auctions)
    except Exception as e:
        print(f"Error updating HTML: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
