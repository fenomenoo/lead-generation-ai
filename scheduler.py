"""
Daily scheduler — runs automatically to:
1. Send any due emails (initial + follow-ups)
2. Log results with timestamps

Run once to start the loop:
  python scheduler.py

Or set it up as a Windows Task Scheduler job to run daily at 9am.
"""
import time
import sys
import os
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("scheduler.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

SEND_HOUR = 9        # Send at 9am
CHECK_INTERVAL = 3600  # Check every hour


def run_daily_send():
    log.info("=== Daily send starting ===")
    try:
        from sender.send import send_due_emails
        send_due_emails(limit=50)
        log.info("=== Daily send complete ===")
    except Exception as e:
        log.error(f"Send failed: {e}")


def main():
    log.info("Scheduler started. Will send emails daily at 9am.")
    last_run_date = None

    while True:
        now = datetime.now()
        today = now.date()

        if now.hour >= SEND_HOUR and last_run_date != today:
            run_daily_send()
            last_run_date = today

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
