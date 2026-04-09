"""
Google Maps lead scraper.
- If GOOGLE_PLACES_API_KEY is set: uses Google Places API (faster, more reliable)
- Otherwise: uses requests-based scraper (no browser needed)
"""
import time
import re
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import GOOGLE_PLACES_API_KEY
from tracker.db import insert_lead

import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def scrape(niche: str, city: str, limit: int = 50) -> list:
    if GOOGLE_PLACES_API_KEY:
        print(f"[Scraper] Using Google Places API for '{niche}' in '{city}'")
        return _scrape_places_api(niche, city, limit)
    else:
        print(f"[Scraper] Using Playwright for '{niche}' in '{city}'")
        return _scrape_playwright(niche, city, limit)


# ── Google Places API path ─────────────────────────────────────────────────

def _scrape_places_api(niche: str, city: str, limit: int) -> list:
    query = f"{niche} in {city}"
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    results = []
    params = {"query": query, "key": GOOGLE_PLACES_API_KEY}

    while len(results) < limit:
        resp = requests.get(url, params=params, timeout=10).json()
        for place in resp.get("results", []):
            lead = {
                "name": place.get("name"),
                "niche": niche,
                "city": city,
                "address": place.get("formatted_address"),
                "phone": None,
                "website": None,
                "rating": place.get("rating"),
                "review_count": place.get("user_ratings_total"),
            }
            place_id = place.get("place_id")
            if place_id:
                details = _get_place_details(place_id)
                lead["phone"] = details.get("phone")
                lead["website"] = details.get("website")
            lead_id = insert_lead(lead)
            lead["id"] = lead_id
            results.append(lead)
            print(f"  [+] {lead['name']} — {lead['website'] or 'no website'}")
            if len(results) >= limit:
                break

        next_page = resp.get("next_page_token")
        if not next_page or len(results) >= limit:
            break
        time.sleep(2)
        params = {"pagetoken": next_page, "key": GOOGLE_PLACES_API_KEY}

    print(f"[Scraper] Done — {len(results)} leads saved.")
    return results


def _get_place_details(place_id: str) -> dict:
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "fields": "formatted_phone_number,website",
        "key": GOOGLE_PLACES_API_KEY,
    }
    resp = requests.get(url, params=params, timeout=10).json()
    result = resp.get("result", {})
    return {
        "phone": result.get("formatted_phone_number"),
        "website": result.get("website"),
    }


# ── Playwright scraper ─────────────────────────────────────────────────────

def _scrape_playwright(niche: str, city: str, limit: int) -> list:
    from playwright.sync_api import sync_playwright

    results = []
    search_query = f"{niche} in {city}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=HEADERS["User-Agent"],
            locale="en-US",
        )
        page = context.new_page()

        maps_url = f"https://www.google.com/maps/search/{requests.utils.quote(search_query)}"
        print(f"  [~] Opening: {maps_url}")
        page.goto(maps_url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)

        # Dismiss Google consent page if present
        if "Before you continue" in page.title():
            for btn_text in ["Accept all", "I agree", "Agree", "Accept"]:
                try:
                    page.click(f'button:has-text("{btn_text}")', timeout=2000)
                    print(f"  [~] Accepted consent: '{btn_text}'")
                    time.sleep(3)
                    break
                except Exception:
                    pass

        # Scroll the results panel to load more listings
        for _ in range(min(limit // 3 + 2, 8)):
            try:
                page.evaluate("""
                    const feed = document.querySelector('div[role="feed"]');
                    if (feed) feed.scrollTop += 1200;
                """)
                time.sleep(1.5)
            except Exception:
                break

        # Collect all listing links
        listing_links = page.locator('a[href*="/maps/place/"]').all()
        hrefs = []
        seen = set()
        for link in listing_links:
            try:
                href = link.get_attribute("href")
                if href and href not in seen and "/maps/place/" in href:
                    seen.add(href)
                    hrefs.append(href)
            except Exception:
                continue

        print(f"  [~] Found {len(hrefs)} listings, processing up to {limit}...")

        for href in hrefs[:limit]:
            try:
                page.goto(href, wait_until="domcontentloaded", timeout=20000)
                time.sleep(2)

                name = _safe_text(page, 'h1')
                address = _safe_text(page, 'button[data-item-id="address"]')
                phone = _safe_text(page, '[data-item-id^="phone"]')
                website = _safe_attr(page, 'a[data-item-id="authority"]', "href") or \
                          _safe_attr(page, 'a[href^="http"]:not([href*="google"])', "href")
                rating_text = _safe_text(page, 'div.F7nice > span[aria-hidden="true"]')
                rating = float(rating_text) if rating_text else None
                review_el = page.locator('div.F7nice').first
                review_text = ""
                try:
                    review_text = review_el.inner_text(timeout=2000)
                except Exception:
                    pass
                review_count = _parse_review_count(review_text)

                if not name:
                    continue

                lead = {
                    "name": name,
                    "niche": niche,
                    "city": city,
                    "address": address,
                    "phone": phone,
                    "website": website,
                    "rating": rating,
                    "review_count": review_count,
                }
                lead_id = insert_lead(lead)
                lead["id"] = lead_id
                results.append(lead)
                print(f"  [+] {name.encode('ascii','ignore').decode()} — {(website or phone or 'no contact').encode('ascii','ignore').decode()}")

            except Exception as e:
                err = str(e).encode('ascii', 'ignore').decode()
                print(f"  [!] Skipped listing: {err}")
                continue

        browser.close()

    print(f"[Scraper] Done — {len(results)} leads saved.")
    return results


# ── Requests-based fallback ────────────────────────────────────────────────

def _safe_text(page, selector: str) -> str:
    try:
        return page.locator(selector).first.inner_text(timeout=2000).strip()
    except Exception:
        return None


def _safe_attr(page, selector: str, attr: str) -> str:
    try:
        return page.locator(selector).first.get_attribute(attr, timeout=2000)
    except Exception:
        return None


def _parse_review_count(text: str) -> int:
    if not text:
        return None
    import re
    nums = re.findall(r"[\d,]+", text)
    if len(nums) > 1:
        return int(nums[1].replace(",", ""))
    return None


def _scrape_requests(niche: str, city: str, limit: int) -> list:
    """
    Scrapes Google Maps via HTTP requests by parsing the embedded JSON data.
    Extracts: name, address, phone, website, rating, review count.
    """
    results = []
    query = f"{niche} {city}"
    encoded = requests.utils.quote(query)

    # Google Maps search URL
    url = f"https://www.google.com/maps/search/{encoded}"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        html = resp.text

        # Extract business listings from embedded JSON
        businesses = _parse_maps_html(html, niche, city)

        if not businesses:
            print("  [!] Google Maps returned no parseable data — trying Google Search fallback...")
            businesses = _scrape_google_search(niche, city, limit)

        for biz in businesses[:limit]:
            lead_id = insert_lead(biz)
            biz["id"] = lead_id
            results.append(biz)
            print(f"  [+] {biz['name']} — {biz.get('website') or biz.get('phone') or 'no contact'}")

    except Exception as e:
        print(f"  [!] Scraper error: {e}")
        print("  [!] Falling back to Google Search scraper...")
        results = _scrape_google_search(niche, city, limit)

    print(f"[Scraper] Done — {len(results)} leads saved.")
    return results


def _parse_maps_html(html: str, niche: str, city: str) -> list:
    """Extract business data from Google Maps page HTML."""
    businesses = []

    # Google Maps embeds data as JSON arrays — extract name/phone/address patterns
    # Pattern: ["Business Name", null, ["address"], null, null, null, null, ["phone"]]
    name_pattern = re.compile(r'"([^"]{3,80})"(?:,null){2},\["([^"]+)"(?:,null)*\]')
    phone_pattern = re.compile(r'\+?[\d\s\-\(\)]{7,20}(?=",)')
    website_pattern = re.compile(r'https?://(?!maps\.google|google\.com|gstatic)[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}(?:/[^\s"]*)?')
    rating_pattern = re.compile(r'"(\d\.\d)",(\d+(?:,\d+)*)')

    # Extract all phone numbers
    phones = phone_pattern.findall(html)
    # Extract all websites
    websites = [w for w in website_pattern.findall(html)
                if not any(x in w for x in ['googleapis', 'gstatic', 'schema.org', 'w3.org'])]
    # Extract ratings
    ratings = rating_pattern.findall(html)

    # Extract names — look for capitalized multi-word strings near addresses
    # Use a simpler heuristic: extract from JSON data blobs
    json_names = re.findall(r'"name":"([^"]{5,60})"', html)
    json_addresses = re.findall(r'"formatted_address":"([^"]+)"', html)
    json_phones = re.findall(r'"formatted_phone_number":"([^"]+)"', html)
    json_websites = re.findall(r'"website":"([^"]+)"', html)
    json_ratings = re.findall(r'"rating":([\d.]+)', html)
    json_reviews = re.findall(r'"user_ratings_total":(\d+)', html)

    # If we got structured JSON data, use it
    if json_names:
        for i, name in enumerate(json_names[:50]):
            biz = {
                "name": name,
                "niche": niche,
                "city": city,
                "address": json_addresses[i] if i < len(json_addresses) else None,
                "phone": json_phones[i] if i < len(json_phones) else None,
                "website": json_websites[i] if i < len(json_websites) else None,
                "rating": float(json_ratings[i]) if i < len(json_ratings) else None,
                "review_count": int(json_reviews[i]) if i < len(json_reviews) else None,
            }
            businesses.append(biz)
        return businesses

    return businesses


def _scrape_google_search(niche: str, city: str, limit: int) -> list:
    """
    Fallback: scrape Google Search results for business listings.
    Extracts business names, websites, and addresses from search snippets.
    """
    businesses = []
    query = f"{niche} {city} contact email"
    encoded = requests.utils.quote(query)
    url = f"https://www.google.com/search?q={encoded}&num=20"

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        html = resp.text

        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")

        # Extract organic results
        for result in soup.select("div.g")[:limit]:
            try:
                title_el = result.select_one("h3")
                link_el = result.select_one("a[href]")
                snippet_el = result.select_one("div.VwiC3b, span.aCOpRe")

                if not title_el:
                    continue

                name = title_el.get_text(strip=True)
                website = None
                if link_el:
                    href = link_el.get("href", "")
                    if href.startswith("http") and "google" not in href:
                        website = href.split("&")[0]

                snippet = snippet_el.get_text(strip=True) if snippet_el else ""

                # Extract phone from snippet
                phone_match = re.search(r'[\+\d][\d\s\-\(\)]{7,18}\d', snippet)
                phone = phone_match.group(0).strip() if phone_match else None

                biz = {
                    "name": name,
                    "niche": niche,
                    "city": city,
                    "address": None,
                    "phone": phone,
                    "website": website,
                    "rating": None,
                    "review_count": None,
                    "description": snippet[:200] if snippet else None,
                }
                lead_id = insert_lead(biz)
                biz["id"] = lead_id
                businesses.append(biz)
                print(f"  [+] {name} — {website or 'no website'}")

            except Exception:
                continue

    except Exception as e:
        print(f"  [!] Google Search fallback error: {e}")

    return businesses
