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

    system_prompt = f"""You are {SENDER_NAME}, a Python automation developer based in Lagos, Nigeria.
You build custom automation tools for businesses — lead generation pipelines, web scraping systems,
outreach automation, AI integrations, and Flask dashboards.
You write cold outreach emails that are direct, specific, and value-focused.
Tone: confident, professional, peer-to-peer — not salesy, not desperate, not generic.
Length: 150-200 words per email. One clear CTA per email.
Never use exclamation marks in subject lines. Never use "I hope this finds you well."
Always make it clear you understand their specific business and what they likely do manually."""

    # Only use name if it looks like a real person's first name
    NOT_NAMES = {
        "digital", "marketing", "agency", "manager", "director", "client", "team",
        "great", "when", "hello", "info", "sales", "contact", "support", "admin",
        "general", "business", "company", "services", "solutions", "group", "media",
        "communications", "consulting", "management", "operations", "the", "our",
        "your", "their", "this", "that", "with", "from", "about", "office",
        "personal", "assistant", "executive", "associate", "coordinator", "specialist",
        "consultant", "analyst", "recruiter", "recruitment", "staffing", "hiring",
        "driven", "leading", "building", "helping", "growing", "centres", "giving"
    }
    owner_parts = owner.split() if owner != "there" else []
    if (len(owner_parts) >= 1
            and owner_parts[0][0].isupper()
            and owner_parts[0].isalpha()
            and len(owner_parts[0]) > 2
            and owner_parts[0].lower() not in NOT_NAMES):
        owner_first = owner_parts[0]
    else:
        owner_first = "there"

    user_prompt = f"""Write a 3-email cold outreach sequence for this business from a Python automation developer.

Business: {business_name}
Niche: {niche}
City: {city}
Contact name: {owner_first}
Website: {website}
About them: {description}

WHO I AM AND WHAT I OFFER (work this into every email naturally):
- I'm a Python developer who builds automation tools that replace manual, repetitive work
- I specialize in: lead generation pipelines, web scraping, outreach automation, AI integrations, Flask dashboards
- I've built systems that scrape thousands of leads from Google Maps and websites, enrich contacts automatically, write AI-personalized emails, and send them — all without manual effort
- My GitHub shows real working projects: github.com/fenomenoo
- I work remotely and am available for freelance projects, contracts, and full-time remote roles
- The pitch: if they're doing lead research, data extraction, outreach, or any repetitive data work manually — I can build a system to automate it and save them significant time and money

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
- initial: open with something specific about their business or niche, identify one thing they likely do manually (lead research, outreach, data collection), show how automation solves it, reference github.com/fenomenoo as proof of work, end with a soft CTA for a quick call or reply
- followup1 (day {FOLLOWUP_1_DAYS}): reference the first email briefly, add a specific example of what I built (e.g. "I built a system that pulled 2,000 leads from Google Maps and sent personalized emails automatically"), re-invite them to chat
- followup2 (day {FOLLOWUP_2_DAYS}): short breakup email, make it easy to say yes or no, leave door open, mention github.com/fenomenoo one last time
- Address contact as Hi {owner_first}
- Sign every email: {SENDER_NAME} | Python Automation Developer | gbolahanlawal57@gmail.com
- Keep it human — no buzzword soup, no corporate speak, no "I am writing to express my interest"
"""

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
