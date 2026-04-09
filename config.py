import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
SENDER_NAME = os.getenv("SENDER_NAME", "Your Name")
SENDER_COMPANY = os.getenv("SENDER_COMPANY", "Your Company")
GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")

DB_PATH = os.path.join(os.path.dirname(__file__), "leads.db")
MAX_EMAILS_PER_DAY = 50
FOLLOWUP_1_DAYS = 3
FOLLOWUP_2_DAYS = 7
