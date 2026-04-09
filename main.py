"""
LeadGen AI — CLI entry point
Usage:
  python main.py setup
  python main.py scrape --niche "roofers" --city "Dallas TX" --limit 50
  python main.py enrich [--limit 50]
  python main.py write-emails [--limit 50]
  python main.py send [--limit 30] [--dry-run]
  python main.py dashboard [--port 5000]
  python main.py status
"""
import argparse
import sys
import os

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(__file__))


def cmd_setup(args):
    from tracker.db import init_db
    init_db()
    # Check for .env
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        example = os.path.join(os.path.dirname(__file__), ".env.example")
        import shutil
        shutil.copy(example, env_path)
        print(f"[Setup] Created .env from .env.example — open it and add your API keys.")
    else:
        print("[Setup] .env already exists.")
    print("[Setup] Done. Run 'python main.py scrape --niche \"roofers\" --city \"Dallas TX\"' to start.")


def cmd_scrape(args):
    from tracker.db import init_db
    from scraper.google_maps import scrape
    init_db()
    scrape(niche=args.niche, city=args.city, limit=args.limit)


def cmd_enrich(args):
    from tracker.db import init_db
    from enricher.enrich import enrich_all
    init_db()
    enrich_all(limit=args.limit if args.limit else None)


def cmd_write(args):
    from tracker.db import init_db
    from ai_writer.generate import write_emails_for_all
    init_db()
    write_emails_for_all(limit=args.limit if args.limit else None)


def cmd_send(args):
    from tracker.db import init_db
    from sender.send import send_due_emails
    init_db()
    send_due_emails(limit=args.limit, dry_run=args.dry_run)


def cmd_dashboard(args):
    from tracker.db import init_db
    from dashboard.app import start
    init_db()
    start(port=args.port, debug=args.debug)


def cmd_status(args):
    from tracker.db import init_db, get_stats
    init_db()
    stats = get_stats()
    print("\n=== LeadGen AI Status ===")
    print(f"Total leads:  {stats['total']}")
    print(f"Emails sent:  {stats['emails_sent']}")
    print(f"\nBy status:")
    for status, count in sorted(stats["by_status"].items()):
        print(f"  {status:<20} {count}")
    replied = stats["by_status"].get("replied", 0)
    rate = (replied / stats["total"] * 100) if stats["total"] > 0 else 0
    print(f"\nReply rate:   {rate:.1f}%")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="LeadGen AI — AI-powered lead generation & outreach",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    # setup
    sub.add_parser("setup", help="Initialize database and create .env file")

    # scrape
    p_scrape = sub.add_parser("scrape", help="Scrape leads from Google Maps")
    p_scrape.add_argument("--niche", required=True, help='e.g. "roofers"')
    p_scrape.add_argument("--city", required=True, help='e.g. "Dallas TX"')
    p_scrape.add_argument("--limit", type=int, default=50, help="Max leads to scrape (default 50)")

    # enrich
    p_enrich = sub.add_parser("enrich", help="Enrich leads with email/owner data from their websites")
    p_enrich.add_argument("--limit", type=int, default=None, help="Max leads to enrich")

    # write-emails
    p_write = sub.add_parser("write-emails", help="Generate AI email sequences for enriched leads")
    p_write.add_argument("--limit", type=int, default=None, help="Max leads to write emails for")

    # send
    p_send = sub.add_parser("send", help="Send due emails via Gmail SMTP")
    p_send.add_argument("--limit", type=int, default=30, help="Max emails to send (default 30)")
    p_send.add_argument("--dry-run", action="store_true", help="Preview without sending")

    # dashboard
    p_dash = sub.add_parser("dashboard", help="Open web dashboard at localhost:5000")
    p_dash.add_argument("--port", type=int, default=5000)
    p_dash.add_argument("--debug", action="store_true")

    # status
    sub.add_parser("status", help="Show campaign stats in terminal")

    args = parser.parse_args()

    dispatch = {
        "setup": cmd_setup,
        "scrape": cmd_scrape,
        "enrich": cmd_enrich,
        "write-emails": cmd_write,
        "send": cmd_send,
        "dashboard": cmd_dashboard,
        "status": cmd_status,
    }

    if not args.command:
        parser.print_help()
        sys.exit(0)

    dispatch[args.command](args)


if __name__ == "__main__":
    main()
