"""
Email sender — sends emails via Gmail SMTP with daily rate limiting.
Handles initial emails and follow-ups based on scheduled_for date.
"""
import smtplib
import sys
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import GMAIL_USER, GMAIL_APP_PASSWORD, SENDER_NAME, MAX_EMAILS_PER_DAY
from tracker.db import get_conn, mark_email_sent, update_lead, get_leads


def send_due_emails(limit: int = None, dry_run: bool = False):
    """Send all emails that are scheduled for today or earlier and not yet sent."""
    conn = get_conn()
    c = conn.cursor()

    now = datetime.now().isoformat()
    rows = c.execute("""
        SELECT e.id, e.lead_id, e.email_type, e.subject, e.body,
               l.name, l.email, l.status
        FROM emails e
        JOIN leads l ON e.lead_id = l.id
        WHERE e.sent_at IS NULL
          AND e.scheduled_for <= ?
          AND l.email IS NOT NULL
          AND l.status NOT IN ('unsubscribed', 'bounced')
        ORDER BY e.scheduled_for ASC
    """, (now,)).fetchall()
    conn.close()

    cap = limit or MAX_EMAILS_PER_DAY
    to_send = list(rows)[:cap]

    if not to_send:
        print("[Sender] No emails due to send.")
        return

    print(f"[Sender] Sending {len(to_send)} emails (dry_run={dry_run})...")

    if not dry_run:
        smtp = _connect_smtp()
    else:
        smtp = None

    sent_count = 0
    for row in to_send:
        email_id, lead_id, email_type, subject, body, biz_name, to_email, lead_status = row
        print(f"  [>] {email_type} -> {biz_name} <{to_email}>")

        if dry_run:
            print(f"      Subject: {subject}")
            print(f"      Body preview: {body[:80]}...")
            sent_count += 1
            continue

        try:
            _send_one(smtp, to_email, biz_name, subject, body)
            mark_email_sent(email_id)
            _update_lead_status(lead_id, email_type)
            sent_count += 1
            print(f"      Sent.")
        except Exception as e:
            print(f"      [!] Failed: {e}")

    if smtp:
        smtp.quit()

    print(f"[Sender] Done — {sent_count} emails sent.")


def _connect_smtp():
    # Try port 587 (STARTTLS) first, fall back to 465 (SSL)
    try:
        smtp = smtplib.SMTP("smtp.gmail.com", 587, timeout=15)
        smtp.ehlo()
        smtp.starttls()
        smtp.ehlo()
        smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        return smtp
    except Exception:
        smtp = smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15)
        smtp.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        return smtp


def _send_one(smtp, to_email: str, biz_name: str, subject: str, body: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{SENDER_NAME} <{GMAIL_USER}>"
    msg["To"] = to_email

    # Plain text version
    text_part = MIMEText(body, "plain")
    msg.attach(text_part)

    smtp.sendmail(GMAIL_USER, to_email, msg.as_string())


def _update_lead_status(lead_id: int, email_type: str):
    status_map = {
        "initial": "contacted",
        "followup1": "followed_up_1",
        "followup2": "followed_up_2",
    }
    new_status = status_map.get(email_type, "contacted")
    update_lead(lead_id, {
        "status": new_status,
        "last_contacted": datetime.now().isoformat()
    })


def mark_replied(lead_id: int):
    """Call this when a lead replies."""
    update_lead(lead_id, {"status": "replied"})
    print(f"[Sender] Lead {lead_id} marked as replied.")


def mark_unsubscribed(lead_id: int):
    """Call this when a lead asks to unsubscribe."""
    update_lead(lead_id, {"status": "unsubscribed"})
    print(f"[Sender] Lead {lead_id} marked as unsubscribed.")
