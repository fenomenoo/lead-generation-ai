"""
One-time OAuth setup for Google Sheets access under sendtohola@gmail.com.
Run this once: python setup_oauth.py
It opens a browser, you click Allow, token is saved — done forever.
"""

import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "token.pkl")
OAUTH_CREDS = os.path.join(os.path.dirname(__file__), "oauth_creds.json")


def get_token():
    creds = None
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(OAUTH_CREDS):
                print("\n[ERROR] oauth_creds.json not found.")
                print("\nSteps to get it:")
                print("1. Go to: https://console.cloud.google.com/apis/credentials")
                print("   (make sure project 'organic-acronym-491809-u7' is selected)")
                print("2. Click '+ CREATE CREDENTIALS' > 'OAuth client ID'")
                print("3. App type: Desktop app > Name: Lead Gen Bot > Create")
                print("4. Click 'DOWNLOAD JSON' > save as oauth_creds.json")
                print("5. Drop oauth_creds.json in:", os.path.dirname(__file__))
                print("6. Run this script again\n")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(OAUTH_CREDS, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "wb") as f:
            pickle.dump(creds, f)

    print("[Auth] Token ready.")
    return creds


if __name__ == "__main__":
    creds = get_token()
    if creds:
        print("[Auth] OAuth setup complete. You can now run: python sync_sheets.py")
