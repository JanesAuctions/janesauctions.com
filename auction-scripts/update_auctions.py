#!/usr/bin/env python3
"""
Scrapes the Jane's Auctions HiBid company page for currently listed
auctions and writes them to auctions.json at the repo root.

Run by .github/workflows/update-auctions.yml on a schedule.
"""
import json
import re
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HIBID_URL = "https://hibid.com/company/150802/janes-auctions"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "auctions.json"

HEADERS = {
    # A normal browser UA avoids some bot-blocking behavior.
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def fetch_auctions():
    resp = requests.get(HIBID_URL, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    auctions = []
    seen_links = set()

    # Auction titles on the company page are links to /auction/<id>/<slug>
    # or /catalog/<id>/<slug>. We grab both forms and dedupe.
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if re.search(r"/(auction|catalog)/\d+/", href):
            title = a.get_text(strip=True)
            if not title:
                continue
            full_url = href if href.startswith("http") else f"https://hibid.com{href}"
            # Prefer the /auction/ link over /catalog/ for the same id if both exist
            auction_id_match = re.search(r"/(?:auction|catalog)/(\d+)/", href)
            auction_id = auction_id_match.group(1) if auction_id_match else full_url

            if auction_id in seen_links:
                continue
            seen_links.add(auction_id)

            auctions.append({"title": title, "url": full_url})

    return auctions


def main():
    try:
        auctions = fetch_auctions()
    except Exception as e:
        print(f"Error fetching auctions: {e}", file=sys.stderr)
        sys.exit(1)

    OUTPUT_PATH.write_text(json.dumps(auctions, indent=2) + "\n")
    print(f"Wrote {len(auctions)} auction(s) to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
