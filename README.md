# Lead Generation AI

> Python-powered B2B lead generation engine — scrapes Google Maps, enriches contacts, writes AI outreach emails, sends and follows up automatically.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Playwright](https://img.shields.io/badge/Playwright-Automation-purple)
![Claude AI](https://img.shields.io/badge/Claude-AI--Powered-orange)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## What It Does

Lead Generation AI is a complete B2B outreach pipeline. Give it a business type and a city — it scrapes Google Maps for matching businesses, crawls their websites to find the decision-maker's name and email, writes personalized AI sales sequences, sends them via Gmail, and follows up automatically on Day 3 and Day 7.

Built with a dual-mode scraper: Google Maps Places API first, Playwright browser automation as fallback. It doesn't stop when one method fails.

---

## Features

- **Dual-Mode Scraping** — Google Maps Places API (fast) with automatic fallback to Playwright headless browser when the API limit is hit
- **Deep Website Enrichment** — Crawls up to 10 pages per company website to find decision-maker names, titles, and email addresses
- **Smart Email Inference** — When no email is found, the system guesses common patterns (first@domain, first.last@domain, etc.) from the domain
- **Email Validation** — 11-rule filter removes bad emails (images, placeholders, test addresses) before anything gets sent
- **AI Email Sequences** — Claude AI writes personalized 3-email outreach sequences per lead — not generic templates
- **Automated Sending** — Gmail SMTP with daily rate limiting (50 emails/day)
- **Follow-up Scheduling** — Queues and sends Day 3 + Day 7 follow-ups automatically
- **Scheduler** — Background scheduler runs daily at 9am without manual intervention
- **Web Dashboard** — Flask UI to view leads, track statuses, and control the pipeline
- **CLI Interface** — Full command-line control with 7 commands

---

## How It Works

```
1. SCRAPE     →   Search Google Maps for businesses by type + city
                  (Places API → Playwright fallback → HTML parser fallback)

2. ENRICH     →   Crawl company websites across 10 URL paths
                  Find decision-maker names + emails
                  Infer email patterns if none found
                  Filter bad emails

3. WRITE      →   Generate AI 3-email sequences with Claude API
                  Personalized per business — not templates

4. SEND       →   Send via Gmail SMTP (rate-limited, 50/day)

5. FOLLOW UP  →   Auto Day 3 + Day 7 follow-ups on schedule

6. TRACK      →   Dashboard shows reply rates, statuses, pipeline health
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Language | Python 3.10+ | Core application |
| Browser automation | Playwright | Google Maps scraping fallback |
| Web scraping | BeautifulSoup4, Requests | Website enrichment |
| AI | Anthropic Claude API | Email sequence generation |
| Email | Gmail SMTP | Sending + scheduling |
| Database | SQLite | Lead + campaign tracking |
| Web UI | Flask 3.1 | Dashboard |
| Scheduler | schedule library | Automated daily sending |
| CLI | argparse | Command-line interface |

---

## Project Structure

```
lead-generation-ai/
├── main.py               # CLI entry point
├── config.py             # Configuration + env variable loading
├── scheduler.py          # Background scheduler — runs daily sends at 9am
├── setup_scheduler.bat   # Windows Task Scheduler setup script
├── run_send.bat          # Quick-run batch file for email sending
├── requirements.txt      # Python dependencies
├── .env.example          # Environment variable template
│
├── tracker/
│   └── db.py             # SQLite schema + all database operations
│
├── scraper/
│   └── google_maps.py    # Dual-mode scraper: Places API + Playwright fallback
│
├── enricher/
│   └── enrich.py         # Decision-maker extraction + email inference + validation
│
├── ai_writer/
│   └── generate.py       # Claude API — writes personalized 3-email sequences
│
├── sender/
│   └── send.py           # Gmail SMTP sender with rate limiting + scheduling
│
├── dashboard/
│   └── app.py            # Flask web app — lead management + campaign control
│
└── templates/            # HTML templates for Flask dashboard
```

---

## Setup

### 1. Clone the repo
```bash
git clone https://github.com/fenomenoo/lead-generation-ai.git
cd lead-generation-ai
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
playwright install chromium
```

### 3. Configure environment
```bash
cp .env.example .env
```
Edit `.env` with your credentials:

```env
ANTHROPIC_API_KEY=your_claude_api_key
GMAIL_USER=your@gmail.com
GMAIL_APP_PASSWORD=your_16_char_app_password
SENDER_NAME=Your Name
SENDER_COMPANY=Your Company
GOOGLE_PLACES_API_KEY=your_google_places_key  # optional but recommended
```

> **Gmail App Password:** Go to myaccount.google.com → Security → 2-Step Verification → App passwords.

> **Google Places API Key:** Go to console.cloud.google.com → Enable "Places API" → Create credentials. Gives 200 free API calls/month.

> **Claude API Key:** Get one at console.anthropic.com

### 4. Initialize database
```bash
python main.py setup
```

---

## CLI Commands

```bash
python main.py --help
```

| Command | Example | What It Does |
|---------|---------|-------------|
| `setup` | `python main.py setup` | Initialize DB and create `.env` file |
| `scrape` | `python main.py scrape --niche "roofers" --city "Lagos Nigeria" --limit 50` | Find businesses on Google Maps |
| `enrich` | `python main.py enrich --limit 50` | Extract decision-maker contacts from websites |
| `write-emails` | `python main.py write-emails --limit 50` | Generate AI email sequences |
| `send` | `python main.py send --limit 30` | Send due emails (add `--dry-run` to preview) |
| `status` | `python main.py status` | View stats: leads, emails sent, reply rate |
| `dashboard` | `python main.py dashboard --port 5000` | Launch web dashboard |

### Full pipeline example
```bash
# 1. Scrape 50 roofing companies in Dallas
python main.py scrape --niche "roofing companies" --city "Dallas TX" --limit 50

# 2. Enrich with decision-maker contacts
python main.py enrich --limit 50

# 3. Write AI email sequences
python main.py write-emails --limit 50

# 4. Preview before sending
python main.py send --limit 30 --dry-run

# 5. Send
python main.py send --limit 30

# 6. Check results
python main.py status
```

---

## Automated Scheduling

To run the daily email sender automatically at 9am:

```bash
# Run as background process
python scheduler.py

# Or set up Windows Task Scheduler
setup_scheduler.bat
```

---

## Configuration Reference

| Variable | Required | Where to Get It |
|----------|----------|----------------|
| `ANTHROPIC_API_KEY` | Yes | console.anthropic.com |
| `GMAIL_USER` | Yes | Your Gmail address |
| `GMAIL_APP_PASSWORD` | Yes | Google Account → Security → App passwords |
| `SENDER_NAME` | Yes | Your name |
| `SENDER_COMPANY` | Yes | Your company name |
| `GOOGLE_PLACES_API_KEY` | No (but recommended) | console.cloud.google.com |

---

## Database Schema

**leads** — All scraped businesses (`new → enriched → emails_written → contacted → replied`)  
**emails** — All email bodies, subjects, send timestamps, and follow-up schedules

---

## Built By

[Gbolahan Lawal](https://github.com/fenomenoo) — Python automation developer based in Lagos, Nigeria.  
Open to remote work and freelance projects. Reach me at gbolahanlawal57@gmail.com
