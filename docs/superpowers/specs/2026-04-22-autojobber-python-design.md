# AutoJobber Python — Design Spec

**Date:** 2026-04-22
**Status:** Approved

---

## Goal

A headless Python bot that runs daily on AWS ECS Fargate, automatically applies to jobs on CakeResume and 104.com.tw, filters for remote-friendly roles, handles AI-powered screening questions via the Claude API, stores results in MySQL, and sends a daily email report.

---

## Architecture Overview

```
EventBridge Scheduler (daily cron)
        ↓
ECS Fargate Task (Docker container)
        ↓
  ┌─────────────────────────────────────┐
  │           Python Bot                │
  │                                     │
  │  1. Load config from S3             │
  │  2. Fetch secrets from Secrets Mgr  │
  │  3. Determine today's search term   │
  │     (round-robin from DB run_log)   │
  │  4. For each enabled site:          │
  │     → Launch Playwright browser     │
  │     → Login                         │
  │     → Search (remote filter on)     │
  │     → For each job:                 │
  │       - Check DB (skip if seen)     │
  │       - Apply                       │
  │       - Handle screening w/ Claude  │
  │       - Save result to MySQL        │
  │  5. Generate & send email report    │
  │  6. Write run summary to run_log    │
  └─────────────────────────────────────┘
        ↓                    ↓
    RDS MySQL              S3
  (results, state)    (resume PDF, config.json)
```

### AWS Services

| Service | Purpose |
|---|---|
| ECS Fargate | Runs Docker container — serverless, no server to maintain |
| EventBridge Scheduler | Triggers the Fargate task on a daily cron schedule |
| ECR | Private Docker image registry |
| RDS MySQL | Managed database — job results and run state |
| S3 | Stores resume PDF and config.json |
| Secrets Manager | Stores all credentials securely |
| CloudWatch Logs | Captures container stdout/stderr |

---

## Project Structure

```
autojobber-py/
├── main.py                  # Entry point — orchestrates a full run
├── Dockerfile               # Container definition
├── requirements.txt
├── .env.example             # Template for local dev secrets
├── config.example.json      # Template for local config
├── config/
│   └── loader.py            # Reads config.json from S3 (prod) or local file (dev)
├── browser/
│   └── browser.py           # Playwright setup: headless Chromium, user agent, delays
├── scrapers/
│   ├── base.py              # Abstract base: login(), collect_links(), apply()
│   ├── cakeresume.py        # CakeResume implementation
│   └── job104.py            # 104.com.tw implementation
├── db/
│   ├── models.py            # SQLAlchemy table definitions
│   └── client.py            # DB connection and session management
├── ai/
│   └── screening.py         # Claude API — answers screening questions given resume text
├── email/
│   └── reporter.py          # Builds and sends daily summary email
└── secrets/
    └── loader.py            # Fetches secrets from Secrets Manager (prod) or .env (dev)
```

Each scraper inherits from `base.py` and implements a common interface, so `main.py` iterates over `[CakeResumeScraper, Job104Scraper]` without site-specific logic at the top level.

---

## Scraper Interface (base.py)

Each scraper must implement:

```python
class BaseScraper:
    def login(self, page) -> None: ...
    def collect_links(self, page, search_term: str, pages: int, remote_only: bool) -> list[str]: ...
    def apply(self, page, url: str, resume_path: str, resume_text: str) -> ApplyResult: ...
```

`ApplyResult` is a dataclass: `status` (applied/failed/skipped), `error` (str|None), `job_updated_at` (str|None), `employer_active_at` (str|None), `screening_links` (list[str]).

---

## Data Model

### `job_applications`

| column | type | notes |
|---|---|---|
| id | INT PK AUTO_INCREMENT | |
| url | VARCHAR(500) | job listing URL |
| site | ENUM('cakeresume','104') | |
| search_term | VARCHAR(100) | term that surfaced this job |
| status | ENUM('applied','failed','skipped') | skipped = already applied or no apply button |
| applied_at | DATETIME | |
| error_message | TEXT | null if successful |
| job_updated_at | VARCHAR(100) | scraped from listing |
| employer_active_at | VARCHAR(100) | scraped from listing |

### `run_log`

| column | type | notes |
|---|---|---|
| id | INT PK AUTO_INCREMENT | |
| run_date | DATE | |
| search_term_used | VARCHAR(100) | |
| term_index | INT | index used in this run (for round-robin) |
| total_applied | INT | |
| total_failed | INT | |
| total_skipped | INT | |
| completed_at | DATETIME | null if run crashed mid-execution |

**Round-robin logic:** `main.py` reads the `term_index` from the most recent `run_log` row, increments it mod the number of terms in config, and picks that term from the list.

---

## S3 Config Format

File: `s3://your-bucket/config.json`

```json
{
  "search_terms": [
    "software engineer",
    "backend developer",
    "python developer",
    "full stack engineer"
  ],
  "pages_per_site": 3,
  "sites": ["cakeresume", "104"],
  "remote_only": true,
  "ai_screening": true,
  "report_email": "your@email.com"
}
```

To change search terms, pages, or disable a site — edit this file in the S3 console. No code deploy needed.

---

## Local Development

An `ENV` variable switches between local and production modes:

- `ENV=local` — reads config from local `config.json`, reads secrets from `.env`, connects to local MySQL
- `ENV=production` — reads config from S3, reads secrets from Secrets Manager, connects to RDS

Local MySQL via Docker:
```bash
docker run -d -p 3306:3306 \
  -e MYSQL_ROOT_PASSWORD=yourpassword \
  -e MYSQL_DATABASE=autojobber \
  mysql:8
```

`.env` structure:
```
ENV=local
CAKERESUME_EMAIL=...
CAKERESUME_PASSWORD=...
JOB104_EMAIL=...
JOB104_PASSWORD=...
CLAUDE_API_KEY=...
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=...
DB_NAME=autojobber
REPORT_EMAIL=...
EMAIL_PASSWORD=...
```

`.env` and local `config.json` are in `.gitignore`. The repo ships with `.env.example` and `config.example.json`.

---

## AI Screening Questions

When a job has screening questions:
- If `ai_screening: true` — `screening.py` calls Claude API (`claude-haiku-4-5`) with the question text and resume text, returns answers, bot fills them in
- If `ai_screening: false` or Claude fails — job is marked `skipped`, URL added to the screening links section of the email report

---

## Email Report

**Subject:** `AutoJobber Daily Report — 2026-04-22 | CakeResume + 104 | "backend developer"`

**Body (plain text):**
```
Run Summary
───────────────────────────────
Search term:   backend developer
Sites:         CakeResume, 104.com.tw
Pages/site:    3
Started:       2026-04-22 09:00:12
Completed:     2026-04-22 09:14:37

Results
───────────────────────────────
Applied:       12
Failed:        2
Skipped:       8

Failed Applications
───────────────────────────────
1. https://cakeresume.com/jobs/xyz — TimeoutError: Apply button not found
2. https://www.104.com.tw/job/abc — Error: Login session expired

Screening Questions (manual review needed)
───────────────────────────────
1. https://cakeresume.com/jobs/def
2. https://www.104.com.tw/job/ghi
```

Failed and screening sections are omitted if empty.

---

## Tech Stack

| Component | Library |
|---|---|
| Browser automation | `playwright` (Python) |
| Database ORM | `sqlalchemy` + `pymysql` |
| AWS SDK | `boto3` |
| AI | `anthropic` (Claude Haiku) |
| PDF parsing | `pdfminer.six` |
| Email | `smtplib` (stdlib) |
| Config/secrets | `boto3` + `python-dotenv` (local) |

---

## Deduplication

Before attempting to apply to any job URL, the bot checks `job_applications` for an existing row with that URL. If found (regardless of status), it skips. This prevents re-applying across daily runs.

---

## Out of Scope

- Frontend / web UI
- Real-time log streaming
- Screenshot capture (URLs saved instead)
- Support for job sites other than CakeResume and 104.com.tw
