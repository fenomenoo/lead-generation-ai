"""
Flask web dashboard for monitoring the lead generation campaigns.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from tracker.db import get_stats, get_leads, get_lead, get_emails_for_lead, update_lead
from scraper.google_maps import scrape
from enricher.enrich import enrich_all
from ai_writer.generate import write_emails_for_all
from sender.send import send_due_emails, mark_replied, mark_unsubscribed

from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__, template_folder="../templates")
app.secret_key = os.urandom(24)


@app.route("/")
def index():
    stats = get_stats()
    return render_template("index.html", stats=stats)


@app.route("/leads")
def leads():
    status_filter = request.args.get("status")
    all_leads = get_leads(status=status_filter)
    return render_template("leads.html", leads=all_leads, status_filter=status_filter)


@app.route("/leads/<int:lead_id>")
def lead_detail(lead_id):
    lead = get_lead(lead_id)
    if not lead:
        flash("Lead not found.", "error")
        return redirect(url_for("leads"))
    emails = get_emails_for_lead(lead_id)
    return render_template("lead_detail.html", lead=lead, emails=emails)


@app.route("/leads/<int:lead_id>/status", methods=["POST"])
def update_status(lead_id):
    new_status = request.form.get("status")
    if new_status in ("replied", "unsubscribed", "bounced", "not_interested"):
        update_lead(lead_id, {"status": new_status})
        flash(f"Status updated to '{new_status}'.", "success")
    return redirect(url_for("lead_detail", lead_id=lead_id))


@app.route("/run", methods=["GET", "POST"])
def run_campaign():
    if request.method == "POST":
        niche = request.form.get("niche", "").strip()
        city = request.form.get("city", "").strip()
        limit = int(request.form.get("limit", 20))
        action = request.form.get("action")

        if action == "scrape" and niche and city:
            try:
                results = scrape(niche, city, limit)
                flash(f"Scraped {len(results)} leads for '{niche}' in '{city}'.", "success")
            except Exception as e:
                flash(f"Scrape error: {e}", "error")

        elif action == "enrich":
            try:
                enrich_all(limit=limit)
                flash("Enrichment complete.", "success")
            except Exception as e:
                flash(f"Enrichment error: {e}", "error")

        elif action == "write":
            try:
                write_emails_for_all(limit=limit)
                flash("Email sequences generated.", "success")
            except Exception as e:
                flash(f"Write error: {e}", "error")

        elif action == "send":
            try:
                send_due_emails(limit=limit, dry_run=False)
                flash(f"Sent up to {limit} emails.", "success")
            except Exception as e:
                flash(f"Send error: {e}", "error")

        elif action == "dry_run":
            try:
                send_due_emails(limit=limit, dry_run=True)
                flash("Dry run complete — check the terminal for preview.", "success")
            except Exception as e:
                flash(f"Dry run error: {e}", "error")

        return redirect(url_for("run_campaign"))

    return render_template("run.html")


def start(host="127.0.0.1", port=5000, debug=False):
    print(f"[Dashboard] Starting at http://{host}:{port}")
    app.run(host=host, port=port, debug=debug)
