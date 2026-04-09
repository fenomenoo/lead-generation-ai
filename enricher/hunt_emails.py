"""
Aggressive email hunter for leads that still have no email.
Tries: extended website pages + Google search for contact info.
"""
import re
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tracker.db import get_conn, update_lead
from enricher.enrich import (
    EMAIL_REGEX, is_bad_email, deep_enrich, _guess_email, HEADERS
)

import requests
from bs4 import BeautifulSoup

EXTRA_PAGES = [
    "/meet-the-team", "/our-story", "/the-team", "/staff",
    "/people", "/founders", "/executives", "/directors",
    "/info", "/reach-us", "/get-in-touch", "/enquiry",
    "/enquiries", "/reach-out", "/connect",
]

GOOGLE_SEARCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )
}


def hunt_all():
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM leads WHERE (email IS NULL OR email = '') ORDER BY id"
    ).fetchall()
    conn.close()

    leads = [dict(r) for r in rows]
    print(f"[Hunter] Hunting emails for {len(leads)} leads with no email...")

    for lead in leads:
        print(f"\n  [>>] {lead['name'][:50]}")
        found_email = None
        found_name = None
        found_title = None

        # Try website extra pages first
        if lead.get("website"):
            result = _hunt_website(lead["website"])
            found_email = result.get("email")
            found_name = result.get("name")
            found_title = result.get("title")
            if found_email:
                print(f"       Found on website: {found_email}")

        # Fall back to Google search
        if not found_email:
            result = _google_hunt(lead["name"], lead.get("city", "Nigeria"))
            found_email = result.get("email")
            found_name = found_name or result.get("name")
            if found_email:
                print(f"       Found via Google: {found_email}")

        if not found_email and found_name and lead.get("website"):
            found_email = _guess_email(found_name, lead["website"])
            if found_email:
                print(f"       Guessed from name: {found_email}")

        if found_email or found_name:
            fields = {"status": "enriched"}
            if found_email:
                fields["email"] = found_email
            if found_name:
                fields["owner_name"] = found_name
            update_lead(lead["id"], fields)
        else:
            print(f"       No email found.")

    print(f"\n[Hunter] Done.")


def _hunt_website(url: str) -> dict:
    if not url.startswith("http"):
        url = "https://" + url
    from urllib.parse import urlparse
    base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"

    all_emails = []
    dm_name = None
    dm_title = None

    for path in EXTRA_PAGES:
        try:
            resp = requests.get(base + path, headers=HEADERS, timeout=8, allow_redirects=True)
            if resp.status_code != 200:
                continue

            emails = [e.lower() for e in EMAIL_REGEX.findall(resp.text) if not is_bad_email(e)]
            all_emails.extend(emails)

            soup = BeautifulSoup(resp.text, "lxml")
            for tag in soup(["script", "style"]):
                tag.decompose()
            text = soup.get_text(separator=" ", strip=True)

            # Hunt decision maker names
            from enricher.enrich import DECISION_MAKER_TITLES, _looks_like_name
            for i, title in enumerate(DECISION_MAKER_TITLES[:8]):  # top 8 titles only
                patterns = [
                    rf"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){{1,3}})[,\s\|]{{1,5}}(?:{re.escape(title)})",
                    rf"(?:{re.escape(title)})[:\s\|]{{1,5}}([A-Z][a-z]+(?:\s+[A-Z][a-z]+){{1,3}})",
                ]
                for pat in patterns:
                    m = re.search(pat, text, re.IGNORECASE)
                    if m:
                        name = m.group(1).strip()
                        if _looks_like_name(name) and 5 < len(name) < 45:
                            dm_name = name
                            dm_title = title
                            break
                if dm_name:
                    break

        except Exception:
            continue

    # Pick best email
    from enricher.enrich import _pick_best_email
    best = _pick_best_email(all_emails, base) if all_emails else None
    return {"email": best, "name": dm_name, "title": dm_title}


def _google_hunt(company_name: str, city: str) -> dict:
    """Search Google for the company's email address."""
    query = f'"{company_name}" {city} email contact CEO OR director OR founder'
    encoded = requests.utils.quote(query)
    url = f"https://www.google.com/search?q={encoded}&num=5"

    try:
        resp = requests.get(url, headers=GOOGLE_SEARCH_HEADERS, timeout=10)
        html = resp.text

        # Extract emails from search results
        emails = [e.lower() for e in EMAIL_REGEX.findall(html) if not is_bad_email(e)]

        # Filter to emails likely belonging to the company
        company_words = re.sub(r'[^\w\s]', '', company_name.lower()).split()
        company_emails = [
            e for e in emails
            if any(word[:5] in e for word in company_words if len(word) > 4)
        ]

        best = company_emails[0] if company_emails else (emails[0] if emails else None)

        # Also try to find a name
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(separator=" ", strip=True)

        from enricher.enrich import DECISION_MAKER_TITLES, _looks_like_name
        dm_name = None
        for title in DECISION_MAKER_TITLES[:6]:
            for pat in [
                rf"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){{1,2}})[,\s]{{1,4}}(?:{re.escape(title)})",
                rf"(?:{re.escape(title)})[,:\s]{{1,4}}([A-Z][a-z]+(?:\s+[A-Z][a-z]+){{1,2}})",
            ]:
                m = re.search(pat, text, re.IGNORECASE)
                if m:
                    name = m.group(1).strip()
                    if _looks_like_name(name):
                        dm_name = name
                        break
            if dm_name:
                break

        return {"email": best, "name": dm_name}

    except Exception:
        return {}
