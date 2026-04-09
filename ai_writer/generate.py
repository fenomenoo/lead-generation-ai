"""
AI Email Writer — uses Claude API to generate personalized
3-touch cold email sequences for each lead.
"""
import sys
import os
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import ANTHROPIC_API_KEY, SENDER_NAME, SENDER_COMPANY, FOLLOWUP_1_DAYS, FOLLOWUP_2_DAYS
from tracker.db import get_leads, insert_email, update_lead

import anthropic

MODEL = "claude-haiku-4-5-20251001"


def write_emails_for_all(limit: int = None):
    # Get leads that are enriched or new (have email address)
    conn_leads = get_leads()
    eligible = [
        l for l in conn_leads
        if l.get("email") and l.get("status") in ("new", "enriched")
    ]
    if limit:
        eligible = eligible[:limit]

    if not eligible:
        print("[Writer] No leads with email addresses found. Run 'enrich' first.")
        return

    print(f"[Writer] Writing email sequences for {len(eligible)} leads...")
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    for lead in eligible:
        print(f"  [~] {lead['name']} ({lead['email']})")
        try:
            sequence = _generate_sequence(client, lead)
            _save_sequence(lead["id"], sequence)
            update_lead(lead["id"], {"status": "emails_written"})
            print(f"       3 emails written.")
        except Exception as e:
            print(f"       [!] Error: {e}")

    print("[Writer] Done.")


def _generate_sequence(client: anthropic.Anthropic, lead: dict) -> dict:
    business_name = lead["name"]
    niche = lead.get("niche", "local business")
    city = lead.get("city", "your area")
    owner = lead.get("owner_name") or "there"
    description = lead.get("description") or f"a {niche} based in {city}"
    website = lead.get("website") or ""

    system_prompt = f"""You are {SENDER_NAME} from {SENDER_COMPANY}, an AI automation specialist
who helps real estate companies and local businesses get significantly more customers using AI.
You write cold outreach emails that are direct, specific, and revenue-focused.
Tone: confident, professional, peer-to-peer — not salesy, not generic, not desperate.
Length: 150-200 words per email. One clear CTA per email.
Never use exclamation marks in subject lines. Never use phrases like "I hope this finds you well."
Always make it clear you understand their business specifically."""

    owner_first = owner.split()[0] if owner != "there" else "there"

    user_prompt = f"""Write a 3-email cold outreach sequence for this real estate company.

Business: {business_name}
City: {city}
Contact name: {owner_first}
Website: {website}
About them: {description}

THE PITCH (work this into every email naturally):
- We build AI-powered systems that automatically find, qualify, and nurture leads for real estate companies
- This means they stop relying on referrals or cold calls and get a consistent pipeline of serious buyers and investors
- Real estate companies using this see 30-50% more qualified inquiries within 60 days
- We handle the full setup — they just handle the conversations with interested clients
- We want to get on a quick call to walk them through exactly how it works for their specific market

Return EXACTLY this JSON (no markdown, no extra text):
{{
  "initial": {{
    "subject": "...",
    "body": "..."
  }},
  "followup1": {{
    "subject": "...",
    "body": "..."
  }},
  "followup2": {{
    "subject": "...",
    "body": "..."
  }}
}}

Email rules:
- initial: open with something specific about their business, explain the AI lead gen system briefly, show the revenue upside (more qualified buyers = more closings), end with a soft CTA to hop on a 15-min call to discuss how we execute this for them specifically
- followup1 (day {FOLLOWUP_1_DAYS}): reference the first email, add urgency or a specific result/stat, mention they can see exactly what the system looks like at theclientmachine.netlify.app, re-invite them to a quick call
- followup2 (day {FOLLOWUP_2_DAYS}): short breakup email, mention the website one last time (theclientmachine.netlify.app) if they want to see how it works, make it easy to say yes or no, leave the door open with no pressure
- Address contact as Hi {owner_first}
- Sign every email: {SENDER_NAME}, {SENDER_COMPANY}
- Keep it human — no buzzword soup, no corporate speak"""

    message = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        messages=[{"role": "user", "content": user_prompt}],
        system=system_prompt,
    )

    import json
    raw = message.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    sequence = json.loads(raw.strip())
    return sequence


def _save_sequence(lead_id: int, sequence: dict):
    now = datetime.now()

    insert_email(
        lead_id=lead_id,
        email_type="initial",
        subject=sequence["initial"]["subject"],
        body=sequence["initial"]["body"],
        scheduled_for=now.isoformat(),
    )
    insert_email(
        lead_id=lead_id,
        email_type="followup1",
        subject=sequence["followup1"]["subject"],
        body=sequence["followup1"]["body"],
        scheduled_for=(now + timedelta(days=FOLLOWUP_1_DAYS)).isoformat(),
    )
    insert_email(
        lead_id=lead_id,
        email_type="followup2",
        subject=sequence["followup2"]["subject"],
        body=sequence["followup2"]["body"],
        scheduled_for=(now + timedelta(days=FOLLOWUP_2_DAYS)).isoformat(),
    )
