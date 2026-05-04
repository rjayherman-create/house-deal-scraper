import requests
from bs4 import BeautifulSoup
import re
import json

# -----------------------------
# HELPERS
# -----------------------------

def normalize(listing):
    """Ensure all sources return the same structure."""
    return {
        "address": listing.get("address", "").strip(),
        "city": listing.get("city", "").strip(),
        "state": listing.get("state", "").strip(),
        "zip_code": listing.get("zip_code", "").strip(),
        "asking_price": float(listing.get("asking_price", 0)),
    }


# -----------------------------
# REDFIN SCRAPER (API)
# -----------------------------

def scrape_redfin(city, state, limit):
    try:
        url = (
            f"https://redfin.com/stingray/api/gis-csv"
            f"?al=1&market={state}&num_homes={limit}&region_id=0"
            f"&region_type=6&status=1&uipt=1,2,3,4,5,6,7"
            f"&v=8&city={city.replace(' ', '%20')}"
        )

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://redfin.com"
        }

        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return []

        lines = resp.text.split("\n")
        results = []

        for line in lines[1:limit+1]:
            parts = line.split(",")
            if len(parts) < 10:
                continue

            results.append({
                "address": parts[2],
                "city": city,
                "state": state,
                "zip_code": parts[3],
                "asking_price": parts[4].replace("$", "").replace(",", "")
            })

        return results

    except Exception:
        return []


# -----------------------------
# ZILLOW SCRAPER (HTML)
# -----------------------------

def scrape_zillow(city, state, limit):
    try:
        search = f"{city} {state}".replace(" ", "-")
        url = f"https://www.zillow.com/homes/{search}_rb/"

        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")

        results = []
        cards = soup.select("article")[:limit]

        for card in cards:
            price = card.select_one("span[data-test='property-card-price']")
            address = card.select_one("address")

            if not price or not address:
                continue

            price_val = re.sub(r"[^\d.]", "", price.text)

            results.append({
                "address": address.text,
                "city": city,
                "state": state,
                "zip_code": "",
                "asking_price": price_val
            })

        return results

    except Exception:
        return []


# -----------------------------
# CRAIGSLIST SCRAPER
# -----------------------------

def scrape_craigslist(city, state, limit):
    try:
        base = f"https://{city.lower()}.craigslist.org"
        url = f"{base}/search/rea"

        resp = requests.get(url, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")

        results = []
        posts = soup.select(".result-row")[:limit]

        for post in posts:
            title = post.select_one(".result-title")
            price = post.select_one(".result-price")

            if not title or not price:
                continue

            price_val = re.sub(r"[^\d.]", "", price.text)

            results.append({
                "address": title.text,
                "city": city,
                "state": state,
                "zip_code": "",
                "asking_price": price_val
            })

        return results

    except Exception:
        return []


# -----------------------------
# FACEBOOK MARKETPLACE SCRAPER
# -----------------------------

def scrape_facebook(city, state, limit):
    """
    FB Marketplace blocks bots heavily.
    We use a fallback HTML scraper with browser headers.
    Works when FB doesn't challenge with login.
    """
    try:
        search = f"{city} {state}".replace(" ", "%20")
        url = f"https://www.facebook.com/marketplace/search/?query={search}"

        headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US,en;q=0.9",
        }

        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")

        results = []
        items = soup.select("a[href*='/marketplace/item']")[:limit]

        for item in items:
            title = item.text.strip()
            price_match = re.search(r"\$([\d,]+)", title)
            price_val = price_match.group(1).replace(",", "") if price_match else "0"

            results.append({
                "address": title,
                "city": city,
                "state": state,
                "zip_code": "",
                "asking_price": price_val
            })

        return results

    except Exception:
        return []


# -----------------------------
# MASTER SCRAPER
# -----------------------------

def scrape_listings(city: str, state: str, limit: int = 20):
    results = []

    sources = [
        scrape_redfin,
        scrape_zillow,
        scrape_craigslist,
        scrape_facebook,
    ]

    for source in sources:
        try:
            listings = source(city, state, limit)
            for item in listings:
                results.append(normalize(item))
        except Exception:
            continue

    # Remove duplicates by address
    seen = set()
    unique = []
    for r in results:
        key = r["address"].lower()
        if key not in seen:
            seen.add(key)
            unique.append(r)

    return unique[:limit]
