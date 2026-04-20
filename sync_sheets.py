"""
Syncs all leads from SQLite to Google Sheets under sendtohola@gmail.com.
Run: python sync_sheets.py
"""

import os
import sqlite3
import gspread

TOKEN_FILE = os.path.join(os.path.dirname(__file__), "token.pkl")
DB_PATH = os.path.join(os.path.dirname(__file__), "leads.db")
SHEET_ID = "1Zy_MANHIxJ0qm-ip1mxLgYILZjukoViCS-tmf0csquo"

HEADERS = [
    "ID", "Business Name", "Niche", "City", "Website",
    "Owner Name", "Email", "Status", "Phone", "Rating",
    "Reviews", "Last Contacted", "Created At"
]

STATUS_COLORS = {
    "new":           {"red": 0.94, "green": 0.94, "blue": 0.94},
    "enriched":      {"red": 0.88, "green": 0.97, "blue": 0.98},
    "emails_written":{"red": 0.93, "green": 0.91, "blue": 0.98},
    "contacted":     {"red": 0.89, "green": 0.94, "blue": 1.0},
    "followed_up_1": {"red": 1.0,  "green": 0.95, "blue": 0.88},
    "followed_up_2": {"red": 0.99, "green": 0.89, "blue": 0.93},
    "replied":       {"red": 0.91, "green": 0.97, "blue": 0.91},
    "skip":          {"red": 0.95, "green": 0.95, "blue": 0.95},
}


def load_creds():
    from google.oauth2.service_account import Credentials
    CREDS_FILE = os.path.join(os.path.dirname(__file__), "google_creds.json")
    scopes = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    return Credentials.from_service_account_file(CREDS_FILE, scopes=scopes)


def get_leads():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, name, niche, city, website, owner_name, email, status, "
        "phone, rating, review_count, last_contacted, created_at "
        "FROM leads ORDER BY id ASC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def sync():
    creds = load_creds()
    if not creds:
        return

    client = gspread.authorize(creds)

    sh = client.open_by_key(SHEET_ID)
    print(f"[Sheets] Opened sheet: {sh.title}")

    ws = sh.sheet1
    ws.clear()

    leads = get_leads()
    rows = [HEADERS] + [[
        r["id"], r["name"], r["niche"], r["city"], r["website"],
        r["owner_name"], r["email"], r["status"], r["phone"],
        r["rating"], r["review_count"], r["last_contacted"], r["created_at"]
    ] for r in leads]

    ws.update("A1", rows, value_input_option="USER_ENTERED")

    # Header formatting
    header_fmt = {
        "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}},
        "backgroundColor": {"red": 0.69, "green": 0.49, "blue": 0.31},
        "horizontalAlignment": "CENTER"
    }
    ws.format("A1:M1", header_fmt)

    # Color rows by status
    requests = []
    sheet_id = ws.id
    for i, lead in enumerate(leads):
        row_index = i + 1  # 0-indexed, skip header
        color = STATUS_COLORS.get(lead["status"], {"red": 1, "green": 1, "blue": 1})
        requests.append({
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": row_index,
                    "endRowIndex": row_index + 1,
                    "startColumnIndex": 0,
                    "endColumnIndex": 13
                },
                "cell": {"userEnteredFormat": {"backgroundColor": color}},
                "fields": "userEnteredFormat.backgroundColor"
            }
        })

    # Freeze header + auto-resize
    requests.append({
        "updateSheetProperties": {
            "properties": {"sheetId": sheet_id, "gridProperties": {"frozenRowCount": 1}},
            "fields": "gridProperties.frozenRowCount"
        }
    })
    requests.append({
        "autoResizeDimensions": {
            "dimensions": {"sheetId": sheet_id, "dimension": "COLUMNS", "startIndex": 0, "endIndex": 13}
        }
    })

    sh.batch_update({"requests": requests})

    url = f"https://docs.google.com/spreadsheets/d/{sh.id}"
    print(f"\n[Sheets] Done — {len(leads)} leads synced")
    print(f"[Sheets] Open here: {url}\n")
    return url


if __name__ == "__main__":
    sync()
