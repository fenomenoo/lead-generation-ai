import sqlite3
from datetime import datetime
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config import DB_PATH


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            niche TEXT,
            city TEXT,
            address TEXT,
            phone TEXT,
            website TEXT,
            email TEXT,
            owner_name TEXT,
            description TEXT,
            rating REAL,
            review_count INTEGER,
            status TEXT DEFAULT 'new',
            created_at TEXT DEFAULT (datetime('now')),
            last_contacted TEXT
        );

        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lead_id INTEGER NOT NULL,
            email_type TEXT NOT NULL,
            subject TEXT,
            body TEXT,
            sent_at TEXT,
            scheduled_for TEXT,
            opened INTEGER DEFAULT 0,
            FOREIGN KEY (lead_id) REFERENCES leads(id)
        );
    """)
    conn.commit()
    conn.close()
    print("[DB] Database initialized.")


def insert_lead(data: dict) -> int:
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT OR IGNORE INTO leads
            (name, niche, city, address, phone, website, rating, review_count, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'new')
    """, (
        data.get("name"), data.get("niche"), data.get("city"),
        data.get("address"), data.get("phone"), data.get("website"),
        data.get("rating"), data.get("review_count")
    ))
    lead_id = c.lastrowid
    conn.commit()
    conn.close()
    return lead_id


def update_lead(lead_id: int, fields: dict):
    conn = get_conn()
    c = conn.cursor()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [lead_id]
    c.execute(f"UPDATE leads SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()


def get_leads(status=None, limit=None):
    conn = get_conn()
    c = conn.cursor()
    query = "SELECT * FROM leads"
    params = []
    if status:
        query += " WHERE status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC"
    if limit:
        query += f" LIMIT {int(limit)}"
    rows = c.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_lead(lead_id: int):
    conn = get_conn()
    c = conn.cursor()
    row = c.execute("SELECT * FROM leads WHERE id = ?", (lead_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def insert_email(lead_id: int, email_type: str, subject: str, body: str, scheduled_for: str = None):
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        INSERT INTO emails (lead_id, email_type, subject, body, scheduled_for)
        VALUES (?, ?, ?, ?, ?)
    """, (lead_id, email_type, subject, body, scheduled_for))
    email_id = c.lastrowid
    conn.commit()
    conn.close()
    return email_id


def get_emails_for_lead(lead_id: int):
    conn = get_conn()
    c = conn.cursor()
    rows = c.execute("SELECT * FROM emails WHERE lead_id = ? ORDER BY id", (lead_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_email_sent(email_id: int):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE emails SET sent_at = ? WHERE id = ?", (datetime.now().isoformat(), email_id))
    conn.commit()
    conn.close()


def get_stats():
    conn = get_conn()
    c = conn.cursor()
    total = c.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    by_status = c.execute(
        "SELECT status, COUNT(*) as cnt FROM leads GROUP BY status"
    ).fetchall()
    emails_sent = c.execute(
        "SELECT COUNT(*) FROM emails WHERE sent_at IS NOT NULL"
    ).fetchone()[0]
    conn.close()
    stats = {"total": total, "emails_sent": emails_sent, "by_status": {}}
    for row in by_status:
        stats["by_status"][row[0]] = row[1]
    return stats
