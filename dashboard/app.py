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


CLIENT_PROJECT_2 = {
    "name": "Crestview Talent",
    "location": "London, UK",
    "niche": "Recruitment Firm",
    "start_date": "February 2026",
    "status": "active",
    "summary": "Crestview Talent is a London-based recruitment firm placing candidates across tech, finance, and operations. Before working with us, their business development team spent 20+ hours a week manually searching LinkedIn for hiring managers, collecting contact details in spreadsheets, and sending one-by-one outreach emails. It was inconsistent, slow, and impossible to scale. We built a fully automated pipeline that identifies companies actively hiring, finds the HR Director or Head of Talent email directly, and sends personalised outreach — freeing their team to focus entirely on placements.",
    "results_summary": "20+ hours/week saved on manual prospecting. 3x increase in outreach volume. 18% average reply rate.",
    "testimonial": "\"Our BD team was drowning in spreadsheets. Now the pipeline runs itself — we just handle the conversations. Best investment we've made this year.\" — Oliver Reed, Managing Partner, Crestview Talent",
    "months": [
        {
            "month": "February 2026",
            "short": "Feb",
            "leads": 95,
            "emails_sent": 82,
            "replies": 14,
            "meetings": 4,
            "deals": 1,
            "reply_rate": "17.1%",
            "note": "Launch month — system built and first batch targeting London tech companies deployed.",
        },
        {
            "month": "March 2026",
            "short": "Mar",
            "leads": 178,
            "emails_sent": 156,
            "replies": 29,
            "meetings": 8,
            "deals": 3,
            "reply_rate": "18.6%",
            "note": "Expanded targeting to finance and operations sectors. Best month so far.",
        },
        {
            "month": "April 2026",
            "short": "Apr",
            "leads": 149,
            "emails_sent": 131,
            "replies": 25,
            "meetings": 7,
            "deals": 2,
            "reply_rate": "19.1%",
            "note": "Best month yet for Crestview. Expanded targeting to Edinburgh and Bristol. March pipeline converted with 2 deals closed and 3 proposals sent.",
        },
        {
            "month": "May 2026",
            "short": "May",
            "leads": 41,
            "emails_sent": 33,
            "replies": 5,
            "meetings": 2,
            "deals": 0,
            "reply_rate": "15.2%",
            "note": "12 days in — strong early signals. Two meetings already booked with heads of talent at fintech firms. On pace to beat April if momentum holds.",
        },
    ]
}

CLIENT_PROJECT = {
    "name": "Vertex Digital",
    "location": "Birmingham, UK",
    "niche": "Digital Marketing Agency",
    "start_date": "December 2025",
    "status": "active",
    "summary": "Vertex Digital approached us in December 2025 needing a scalable outreach system to grow their client base. They were generating leads manually — slow, inconsistent, and expensive in staff time. We built a fully automated pipeline that scrapes decision makers across UK businesses, enriches contacts with verified personal emails, and sends AI-personalised outreach sequences with automatic follow-ups.",
    "results_summary": "150+ new leads generated monthly. 20% increase in response rate. 2.3% increase in closed deal rate.",
    "testimonial": "\"Before this system we were lucky to get 2 or 3 responses a month from cold outreach. Now we're booking meetings on autopilot. It completely changed how we do business development.\" — Marcus T., Managing Director, Vertex Digital",
    "months": [
        {
            "month": "December 2025",
            "short": "Dec",
            "leads": 80,
            "emails_sent": 65,
            "replies": 9,
            "meetings": 2,
            "deals": 1,
            "reply_rate": "13.8%",
            "note": "Launch month — system configured and first campaign deployed mid-December.",
        },
        {
            "month": "January 2026",
            "short": "Jan",
            "leads": 160,
            "emails_sent": 143,
            "replies": 27,
            "meetings": 7,
            "deals": 3,
            "reply_rate": "18.9%",
            "note": "Full month running. Client started targeting London and Manchester in addition to Birmingham.",
        },
        {
            "month": "February 2026",
            "short": "Feb",
            "leads": 155,
            "emails_sent": 138,
            "replies": 29,
            "meetings": 8,
            "deals": 4,
            "reply_rate": "21.0%",
            "note": "Consistent performance. Best reply rate month. Follow-up sequences optimised.",
        },
        {
            "month": "March 2026",
            "short": "Mar",
            "leads": 110,
            "emails_sent": 94,
            "replies": 16,
            "meetings": 5,
            "deals": 6,
            "reply_rate": "17.0%",
            "note": "Slower month for new replies but highest deals closed — pipeline from Jan/Feb converted.",
        },
        {
            "month": "April 2026",
            "short": "Apr",
            "leads": 138,
            "emails_sent": 119,
            "replies": 22,
            "meetings": 6,
            "deals": 3,
            "reply_rate": "18.5%",
            "note": "Strong finish to Q1. Reactivated cold leads from January pipeline — 3 deals closed including first enterprise-tier client. Two discovery calls still in progress.",
        },
        {
            "month": "May 2026",
            "short": "May",
            "leads": 38,
            "emails_sent": 29,
            "replies": 4,
            "meetings": 1,
            "deals": 0,
            "reply_rate": "13.8%",
            "note": "Early days — 12 days in. First batch targeting Manchester SaaS companies deployed. One meeting already booked for end of month.",
        },
    ]
}

CLIENT_PROJECT_3 = {
    "name": "Keystone Realty Partners",
    "location": "Austin, TX — USA",
    "niche": "Real Estate Agency",
    "start_date": "February 2026",
    "status": "active",
    "summary": "Keystone Realty Partners is a mid-size real estate brokerage based in Austin, Texas, with agents covering Austin, Houston, and Dallas. Their challenge was simple: too many agents, not enough qualified buyer and seller leads coming in consistently. Cold calling was eating hours. We deployed a targeted outreach pipeline that identifies homeowners, landlords, and property investors across Texas metros, enriches verified contact details, and sends personalised sequences — driving inbound conversations without any cold calling.",
    "results_summary": "3x increase in inbound lead conversations. 19% average reply rate across Texas markets. 6 transactions directly attributed to outreach pipeline.",
    "testimonial": "\"We were spending $3,000/month on Zillow leads that barely converted. This system costs a fraction and the conversations are warmer because they're personalised. Our agents are talking to real people, not tyre-kickers.\" — Rachel Nguyen, Broker-Owner, Keystone Realty Partners",
    "months": [
        {
            "month": "February 2026",
            "short": "Feb",
            "leads": 72,
            "emails_sent": 61,
            "replies": 8,
            "meetings": 2,
            "deals": 1,
            "reply_rate": "13.1%",
            "note": "Launch month. System configured for Austin market — targeting residential investors and landlords with 2+ properties. First deal closed within 3 weeks.",
        },
        {
            "month": "March 2026",
            "short": "Mar",
            "leads": 145,
            "emails_sent": 128,
            "replies": 24,
            "meetings": 6,
            "deals": 2,
            "reply_rate": "18.8%",
            "note": "Expanded to Houston and Dallas. Multi-city targeting working well — reply rates up significantly. Two new listing agreements signed.",
        },
        {
            "month": "April 2026",
            "short": "Apr",
            "leads": 162,
            "emails_sent": 141,
            "replies": 28,
            "meetings": 8,
            "deals": 3,
            "reply_rate": "19.9%",
            "note": "Best month to date. Highest meetings and deals. Follow-up sequences from March converting strongly. Team expanded targeting to San Antonio.",
        },
        {
            "month": "May 2026",
            "short": "May",
            "leads": 47,
            "emails_sent": 38,
            "replies": 6,
            "meetings": 2,
            "deals": 0,
            "reply_rate": "15.8%",
            "note": "12 days in. Two meetings already confirmed. April pipeline still converting — one deal expected to close before end of month.",
        },
    ]
}

CLIENT_PROJECT_4 = {
    "name": "Novacore Technologies",
    "location": "Barcelona, Spain — Europe",
    "niche": "B2B SaaS",
    "start_date": "March 2026",
    "status": "active",
    "summary": "Novacore Technologies is a Barcelona-based B2B SaaS company offering project management tools for construction and engineering firms across Southern Europe. Their sales team was relying entirely on inbound and referrals — slow, unpredictable, and hard to scale. We built a cold outreach engine targeting operations managers and procurement leads at mid-size construction firms in Spain, Italy, and Portugal. AI-personalised emails reference company-specific context, driving qualified conversations with decision makers who'd never heard of Novacore.",
    "results_summary": "Pipeline grew 4x in 60 days. 18.8% average reply rate across Spain, Italy, Portugal. 4 enterprise trials initiated directly from outreach.",
    "testimonial": "\"We'd tried LinkedIn outreach before and got nothing. This is completely different — the emails feel personal, people actually respond, and the quality of conversations is much higher than anything we'd done before.\" — Jordi Mas, Head of Growth, Novacore Technologies",
    "months": [
        {
            "month": "March 2026",
            "short": "Mar",
            "leads": 88,
            "emails_sent": 74,
            "replies": 13,
            "meetings": 3,
            "deals": 1,
            "reply_rate": "17.6%",
            "note": "Launch month targeting Spain. Construction and engineering firms in Madrid and Barcelona. Strong early signals — 3 discovery calls booked in first 3 weeks.",
        },
        {
            "month": "April 2026",
            "short": "Apr",
            "leads": 134,
            "emails_sent": 117,
            "replies": 22,
            "meetings": 6,
            "deals": 3,
            "reply_rate": "18.8%",
            "note": "Expanded to Italy and Portugal. Multi-language sequences deployed. Best month — 3 deals closed including first enterprise trial in Milan.",
        },
        {
            "month": "May 2026",
            "short": "May",
            "leads": 44,
            "emails_sent": 35,
            "replies": 5,
            "meetings": 1,
            "deals": 0,
            "reply_rate": "14.3%",
            "note": "12 days in. Greece and southern France added to targeting list. One enterprise demo booked with a Lisbon-based infrastructure firm.",
        },
    ]
}

PAST_CAMPAIGNS = []

FICTIONAL_REPLIES = [
    {"name": "Pinnacle Digital Agency", "email": "james@pinnacledigital.co.uk", "city": "Birmingham UK"},
    {"name": "Harlow Marketing Group", "email": "sarah.h@harlowmarketing.co.uk", "city": "Manchester UK"},
    {"name": "Bluewave Creative Ltd", "email": "tom@bluewavecreative.co.uk", "city": "London UK"},
    {"name": "Meridian Growth Partners", "email": "dan@meridiangrowth.co.uk", "city": "Leeds UK"},
    {"name": "Stackhouse Media", "email": "claire@stackhousemedia.co.uk", "city": "Bristol UK"},
]

@app.route("/")
def index():
    stats = get_stats()
    stats["recent_replies"] = FICTIONAL_REPLIES
    stats["total"] = 389
    stats["contacted"] = 312
    stats["emails_sent"] = 341
    stats["replied"] = 5
    stats["reply_rate"] = 1.6
    stats["by_status"] = {
        "new": 42,
        "enriched": 35,
        "emails_written": 0,
        "contacted": 168,
        "followed_up_1": 139,
        "followed_up_2": 0,
        "replied": 5,
        "skip": 0,
    }
    return render_template("index.html", stats=stats, past_campaigns=PAST_CAMPAIGNS)


PROJECT_MAP = {
    "1": CLIENT_PROJECT,
    "2": CLIENT_PROJECT_2,
    "3": CLIENT_PROJECT_3,
    "4": CLIENT_PROJECT_4,
}

@app.route("/campaigns")
def campaigns():
    project_id = request.args.get("project", "1")
    project = PROJECT_MAP.get(project_id, CLIENT_PROJECT)
    selected = request.args.get("month", project["months"][-1]["short"])
    active_month = next((m for m in project["months"] if m["short"] == selected), project["months"][-1])
    return render_template("campaigns.html", project=project, active_month=active_month, project_id=project_id)


@app.route("/case-studies")
def case_studies():
    return render_template("case_studies.html", projects=[
        {"id": "1", "project": CLIENT_PROJECT},
        {"id": "2", "project": CLIENT_PROJECT_2},
        {"id": "3", "project": CLIENT_PROJECT_3},
        {"id": "4", "project": CLIENT_PROJECT_4},
    ])


@app.route("/pitch")
def pitch():
    return render_template("pitch.html")


FICTIONAL_REPLIED_LEADS = [
    {"id": 1, "name": "Pinnacle Digital Agency", "niche": "marketing agency", "city": "Birmingham UK", "owner_name": "James Whitfield", "email": "james@pinnacledigital.co.uk", "status": "replied", "last_contacted": "2026-04-12"},
    {"id": 2, "name": "Harlow Marketing Group", "niche": "marketing agency", "city": "Manchester UK", "owner_name": "Sarah Harlow", "email": "sarah.h@harlowmarketing.co.uk", "status": "replied", "last_contacted": "2026-04-11"},
    {"id": 3, "name": "Bluewave Creative Ltd", "niche": "digital agency", "city": "London UK", "owner_name": "Tom Bridges", "email": "tom@bluewavecreative.co.uk", "status": "replied", "last_contacted": "2026-04-10"},
    {"id": 4, "name": "Meridian Growth Partners", "niche": "digital agency", "city": "Leeds UK", "owner_name": "Dan Meridian", "email": "dan@meridiangrowth.co.uk", "status": "replied", "last_contacted": "2026-04-09"},
    {"id": 5, "name": "Stackhouse Media", "niche": "marketing agency", "city": "Bristol UK", "owner_name": "Claire Stackhouse", "email": "claire@stackhousemedia.co.uk", "status": "replied", "last_contacted": "2026-04-08"},
]

@app.route("/leads")
def leads():
    status_filter = request.args.get("status")
    if status_filter == "replied":
        return render_template("leads.html", leads=FICTIONAL_REPLIED_LEADS, status_filter=status_filter)
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
