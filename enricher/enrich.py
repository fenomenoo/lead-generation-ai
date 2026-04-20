"""
Lead enricher: deep scrapes each lead's website to find
- Decision maker names (CEO, MD, Founder, Marketing Manager)
- Real email addresses
- Business description
Also guesses email patterns when name is found but no email.
"""
import re
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tracker.db import get_leads, get_conn, update_lead
from dotenv import load_dotenv
load_dotenv()

import requests
from bs4 import BeautifulSoup

PROSPEO_API_KEY = os.getenv("PROSPEO_API_KEY", "")

# Import Snov module
try:
    from enricher.snov import find_decision_maker_snov, find_by_name_snov
    SNOV_ENABLED = bool(os.getenv("SNOV_CLIENT_ID"))
except ImportError:
    SNOV_ENABLED = False


def prospeo_find_email(full_name: str, domain: str) -> str | None:
    """Query Prospeo Enrich Person API to find a real email for a named person at a domain."""
    if not PROSPEO_API_KEY or not full_name or not domain:
        return None
    parts = full_name.strip().split()
    if len(parts) < 2:
        return None
    first, last = parts[0], parts[-1]
    try:
        resp = requests.post(
            "https://api.prospeo.io/enrich-person",
            headers={"Content-Type": "application/json", "X-KEY": PROSPEO_API_KEY},
            json={"data": {"first_name": first, "last_name": last, "company_website": domain}},
            timeout=10,
        )
        data = resp.json()
        if not data.get("error") and data.get("person"):
            email_obj = data["person"].get("email", {})
            email = email_obj.get("email", "")
            status = email_obj.get("status", "")
            # Only return if not masked and status is good
            if email and "*" not in email and status in ("VERIFIED", "ACCEPT_ALL", "VALID"):
                return email
    except Exception:
        pass
    return None

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}
TIMEOUT = 10

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# Titles we care about — ordered by priority
DECISION_MAKER_TITLES = [
    "ceo", "chief executive", "managing director", "md", "founder",
    "co-founder", "director", "president", "head of marketing",
    "marketing manager", "marketing director", "business development",
    "head of sales", "sales director", "general manager", "gm",
    "principal", "partner", "proprietor", "owner",
]

# Pages to scrape per domain
PAGES_TO_TRY = [
    "", "/about", "/about-us", "/our-team", "/team",
    "/management", "/leadership", "/contact", "/contact-us",
    "/who-we-are", "/company",
]

# Obviously bad emails to reject
BAD_EMAIL_PATTERNS = [
    r"\.webp$", r"\.png$", r"\.jpg$", r"\.gif$", r"\.svg$", r"\.css$", r"\.js$",
    r"^name@", r"^email@", r"^user@", r"^test@", r"^example@",
    r"@example\.", r"@domain\.", r"@email\.", r"@sentry\.", r"@wix\.",
    r"@schema\.", r"@w3\.", r"@gstatic\.", r"@googleapis\.",
    r"admission@examplemail", r"john@gmail\.com$",
]


def is_bad_email(email: str) -> bool:
    email = email.lower().strip()
    for pattern in BAD_EMAIL_PATTERNS:
        if re.search(pattern, email):
            return True
    return False


def enrich_all(limit: int = None, re_enrich: bool = False):
    """
    Enrich leads. By default only processes leads without a good email.
    Pass re_enrich=True to re-process all leads.
    """
    conn = get_conn()
    rows = conn.execute("SELECT * FROM leads ORDER BY id").fetchall()
    conn.close()

    leads = [dict(r) for r in rows]

    # Filter to leads that need work
    to_process = []
    for lead in leads:
        email = lead.get("email") or ""
        needs_work = (
            not email or
            is_bad_email(email) or
            re_enrich
        )
        if needs_work and lead.get("website"):
            to_process.append(lead)
        elif needs_work and not lead.get("website"):
            print(f"  [-] {lead['name'][:40]} — no website, skipping")

    if limit:
        to_process = to_process[:limit]

    print(f"[Enricher] Deep-enriching {len(to_process)} leads...")

    for lead in to_process:
        print(f"\n  [~] {lead['name'][:50]}")
        print(f"      website: {lead['website']}")
        result = deep_enrich(lead["website"])

        fields = {}

        # Update email only if we found something better
        if result.get("email") and not is_bad_email(result["email"]):
            fields["email"] = result["email"]
            print(f"      email: {result['email']}")
        elif lead.get("email") and is_bad_email(lead["email"]):
            fields["email"] = None  # Clear the bad email
            print(f"      cleared bad email: {lead['email']}")

        if result.get("decision_maker_name"):
            fields["owner_name"] = result["decision_maker_name"]
            print("      decision maker: {} ({})".format(
                result['decision_maker_name'].encode('ascii', 'replace').decode(),
                result.get('decision_maker_title', '').encode('ascii', 'replace').decode()
            ))

        # If no email found from website, try Snov (domain search) first
        from urllib.parse import urlparse
        domain = urlparse(lead.get("website", "")).netloc.replace("www.", "")

        if not fields.get("email") and SNOV_ENABLED and domain:
            snov_result = find_decision_maker_snov(domain)
            if snov_result:
                fields["email"] = snov_result["email"]
                if not fields.get("owner_name"):
                    fields["owner_name"] = snov_result["name"]
                print(f"      snov email: {snov_result['email']} ({snov_result['name']}, {snov_result['title']})")

        # If we have a name but still no email, try Prospeo
        if not fields.get("email") and result.get("decision_maker_name"):
            prospeo_email = prospeo_find_email(result["decision_maker_name"], domain)
            if prospeo_email:
                fields["email"] = prospeo_email
                print(f"      prospeo email: {prospeo_email}")

        if result.get("guessed_email"):
            if not fields.get("email"):
                fields["email"] = result["guessed_email"]
                print(f"      guessed email: {result['guessed_email']} (pattern-based)")

        if result.get("description"):
            fields["description"] = result["description"]

        if fields:
            if fields.get("email") or fields.get("owner_name"):
                fields["status"] = "enriched"
            update_lead(lead["id"], fields)
        else:
            print(f"      no decision maker or email found")

    print(f"\n[Enricher] Done.")


def deep_enrich(url: str) -> dict:
    if not url.startswith("http"):
        url = "https://" + url

    base = _get_base_url(url)
    result = {
        "email": None,
        "decision_maker_name": None,
        "decision_maker_title": None,
        "guessed_email": None,
        "description": None,
    }

    all_text = ""
    all_emails = []
    dm_candidates = []  # (name, title, email, priority)

    for path in PAGES_TO_TRY:
        page_url = base.rstrip("/") + path
        try:
            resp = requests.get(page_url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, "lxml")

            # Extract emails from raw HTML
            raw_emails = EMAIL_REGEX.findall(resp.text)
            for e in raw_emails:
                e = e.lower().strip()
                if not is_bad_email(e):
                    all_emails.append(e)

            # Clean up soup for text extraction
            for tag in soup(["script", "style", "nav", "footer", "meta", "link"]):
                tag.decompose()
            text = soup.get_text(separator=" ", strip=True)
            all_text += " " + text

            # Look for decision makers on this page
            candidates = _extract_decision_makers(soup, text, all_emails)
            dm_candidates.extend(candidates)

            # Extract description from homepage only
            if path == "" and not result["description"]:
                result["description"] = _extract_description(text)

        except Exception:
            continue

    # Pick best decision maker
    if dm_candidates:
        # Sort by priority (lower = better title)
        dm_candidates.sort(key=lambda x: x[3])
        best = dm_candidates[0]
        result["decision_maker_name"] = best[0]
        result["decision_maker_title"] = best[1]
        if best[2] and not is_bad_email(best[2]):
            result["email"] = best[2]

    # Pick best generic email if no DM email found
    if not result["email"] and all_emails:
        result["email"] = _pick_best_email(all_emails, base)

    # If we have a name but no email, guess it
    if result["decision_maker_name"] and not result["email"]:
        result["guessed_email"] = _guess_email(result["decision_maker_name"], base)

    return result


def _get_base_url(url: str) -> str:
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _extract_decision_makers(soup, text: str, emails: list) -> list:
    """
    Find decision maker names and their associated emails.
    Returns list of (name, title, email, priority).
    """
    candidates = []

    # Strategy 1: Look for structured team/leadership sections
    # Common patterns: "John Smith, CEO" or "CEO: John Smith"
    title_patterns = []
    for i, title in enumerate(DECISION_MAKER_TITLES):
        priority = i  # lower index = higher priority title
        # Pattern: Name followed by title
        p1 = re.compile(
            rf"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){{1,3}})"  # Name
            rf"[,\s\|–\-]{{1,5}}"                         # separator
            rf"(?:{re.escape(title)})",
            re.IGNORECASE
        )
        # Pattern: Title followed by name
        p2 = re.compile(
            rf"(?:{re.escape(title)})"
            rf"[:\s\|–\-]{{1,5}}"
            rf"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){{1,3}})",
            re.IGNORECASE
        )
        for pattern in [p1, p2]:
            for match in pattern.finditer(text):
                name = match.group(1).strip()
                if 4 < len(name) < 50 and _looks_like_name(name):
                    # Try to find associated email
                    dm_email = _find_email_near_name(text, name, emails)
                    candidates.append((name, title, dm_email, priority))

    # Strategy 2: Look for mailto links near title keywords
    for a_tag in soup.find_all("a", href=re.compile(r"^mailto:")):
        email = a_tag["href"].replace("mailto:", "").split("?")[0].strip().lower()
        if is_bad_email(email):
            continue
        # Check surrounding text for title
        parent_text = ""
        for parent in a_tag.parents:
            parent_text = parent.get_text(separator=" ", strip=True)[:300]
            break
        for i, title in enumerate(DECISION_MAKER_TITLES):
            if title in parent_text.lower():
                # Try to extract name from surrounding text
                name_match = re.search(
                    r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})", parent_text
                )
                name = name_match.group(1) if name_match else None
                if name and _looks_like_name(name):
                    candidates.append((name, title, email, i))
                else:
                    # No name, but email near a title — still valuable
                    candidates.append((None, title, email, i + 100))

    return candidates


def _find_email_near_name(text: str, name: str, emails: list) -> str:
    """Look for an email address within 200 chars of a person's name."""
    idx = text.lower().find(name.lower())
    if idx == -1:
        return None
    snippet = text[max(0, idx-50):idx+250]
    found = EMAIL_REGEX.findall(snippet)
    for e in found:
        e = e.lower()
        if not is_bad_email(e):
            return e
    return None


def _pick_best_email(emails: list, base_url: str) -> str:
    """Pick the best email from a list — prefer domain-matching, non-generic."""
    from urllib.parse import urlparse
    domain = urlparse(base_url).netloc.lower().replace("www.", "")

    generic_prefixes = {"info", "contact", "hello", "admin", "mail",
                        "office", "support", "enquiries", "enquiry", "sales"}

    # Prefer emails matching the company domain
    domain_emails = [e for e in emails if domain.split(".")[0] in e]

    # Among domain emails, prefer non-generic
    personal = [e for e in domain_emails if e.split("@")[0] not in generic_prefixes]
    if personal:
        return sorted(personal)[0]
    if domain_emails:
        return sorted(domain_emails)[0]

    # Fall back to any non-generic email
    non_generic = [e for e in emails if e.split("@")[0] not in generic_prefixes]
    if non_generic:
        return sorted(non_generic)[0]

    return emails[0] if emails else None


def _guess_email(name: str, base_url: str) -> str:
    """Generate likely email patterns for a person at a company domain."""
    from urllib.parse import urlparse
    domain = urlparse(base_url).netloc.lower().replace("www.", "")

    parts = name.lower().split()
    if len(parts) < 2:
        return None

    first, last = parts[0], parts[-1]
    # Most common patterns, in order of likelihood
    patterns = [
        f"{first}@{domain}",
        f"{first}.{last}@{domain}",
        f"{first[0]}{last}@{domain}",
        f"{first}{last[0]}@{domain}",
    ]
    return patterns[0]  # Return most likely pattern


def _looks_like_name(text: str) -> bool:
    """Sanity check — reject obvious non-names."""
    bad_words = {"about", "contact", "services", "properties", "realty",
                 "estate", "homes", "limited", "nigeria", "lagos", "abuja",
                 "click", "learn", "read", "more", "view", "find", "follow"}
    words = text.lower().split()
    return not any(w in bad_words for w in words) and len(words) >= 2


def _extract_description(text: str) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    for s in sentences:
        s = s.strip()
        if 40 < len(s) < 250 and not any(
            skip in s.lower() for skip in ["cookie", "javascript", "privacy", "terms"]
        ):
            return s
    return None
