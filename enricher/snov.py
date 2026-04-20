"""
Snov.io API integration for finding decision maker emails.

Uses v2 API with Bearer token auth.
"""
import requests
import os
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID     = os.getenv("SNOV_CLIENT_ID")
CLIENT_SECRET = os.getenv("SNOV_CLIENT_SECRET")
V1_BASE       = "https://api.snov.io/v1"
V2_BASE       = "https://api.snov.io/v2"

# Cache token in memory for the session
_access_token = None

# Job titles to prioritize — in order of preference
PRIORITY_TITLES = [
    "founder", "co-founder", "owner", "ceo", "chief executive",
    "managing director", "md", "president", "principal",
    "head of growth", "head of marketing", "marketing manager",
    "marketing director", "growth manager", "director of marketing",
    "cmo", "vp marketing", "vp of marketing",
    "office manager", "practice manager", "dental director",
]


def get_access_token() -> str:
    """Get OAuth2 access token from Snov.io (cached per session)."""
    global _access_token
    if _access_token:
        return _access_token

    resp = requests.post(f"{V1_BASE}/oauth/access_token", data={
        "grant_type":    "client_credentials",
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
    }, timeout=10)
    resp.raise_for_status()
    _access_token = resp.json().get("access_token", "")
    return _access_token


def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {get_access_token()}"}


def _score_title(title: str) -> int:
    """Score a job title — higher = more senior/relevant."""
    title_lower = title.lower()
    for i, keyword in enumerate(PRIORITY_TITLES):
        if keyword in title_lower:
            return len(PRIORITY_TITLES) - i
    return 0


def find_decision_maker_snov(domain: str) -> dict | None:
    """
    Search Snov.io for decision makers at a domain.
    Returns best match as {"name": ..., "email": ..., "title": ...} or None.
    """
    try:
        resp = requests.get(
            f"{V2_BASE}/domain-emails-with-info",
            params={"domain": domain, "type": "personal", "limit": 10},
            headers=_auth_headers(),
            timeout=15
        )
        data = resp.json()

        if not data.get("success"):
            return None

        emails = data.get("data", [])
        if not emails:
            return None

        # Score each result by title seniority
        scored = []
        for e in emails:
            first = e.get("first_name", "")
            last  = e.get("last_name", "")
            name  = f"{first} {last}".strip()
            email = e.get("email", "")
            title = e.get("position", "")
            status = e.get("status", "")

            if not email or not name:
                continue

            # Prefer verified emails
            bonus = 5 if status == "verified" else 0
            score = _score_title(title) + bonus
            scored.append((score, {
                "name":  name,
                "email": email,
                "title": title or "Decision Maker",
            }))

        if not scored:
            return None

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[0][1]

    except Exception as e:
        print(f"  Snov.io error: {e}")
        return None


def find_by_name_snov(first: str, last: str, domain: str) -> str:
    """
    Use Snov.io email-finder with a known name + domain.
    Returns email string or empty string.
    """
    try:
        resp = requests.post(
            f"{V1_BASE}/get-emails-from-names",
            json={
                "access_token": get_access_token(),
                "firstName":    first,
                "lastName":     last,
                "domain":       domain,
            },
            timeout=15
        )
        data = resp.json()
        emails = data.get("emails", [])
        if emails:
            return emails[0].get("email", "")
    except Exception as e:
        print(f"  Snov.io name lookup error: {e}")
    return ""
