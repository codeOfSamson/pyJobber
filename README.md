# AutoJobber

A job application bot that automatically applies to jobs on CakeResume and 104.com.tw, then emails you a daily summary. Runs on AWS ECS Fargate via a daily EventBridge schedule.

## How it works

1. EventBridge triggers an ECS Fargate task once daily
2. The task logs in to each configured job site, collects job links, and applies to each one
3. Results (applied, skipped, failed) are stored in RDS MySQL
4. A summary email is sent when the run completes

## Local setup

**Requirements:** Python 3.10+, Docker Desktop, AWS CLI

```bash
pip3 install -r requirements.txt
python3 -m playwright install chromium
```

Copy and fill in credentials:
```bash
cp .env.example .env
cp config.example.json config.json
```

Save 104.com.tw session (login manually including OTP, then close the browser):
```bash
python3 -m playwright codegen --save-storage=auth_104.json https://www.104.com.tw/
```

Run locally (opens a visible browser):
```bash
set -a; source .env; set +a
python3 main.py
```

## Configuration

`config.json`:
| Field | Description |
|---|---|
| `search_terms` | Keywords to search — one is picked per run in round-robin order |
| `pages_per_site` | Search result pages to scrape per run |
| `max_links_per_site` | Cap on job links processed per run |
| `sites` | `"cakeresume"`, `"104"`, or both |
| `remote_only` | Filter for remote jobs only |
| `report_email` | Address to receive the daily summary |

`.env` required keys:
```
DB_HOST, DB_USER, DB_PASSWORD, DB_NAME
CAKERESUME_EMAIL, CAKERESUME_PASSWORD
JOB104_EMAIL, JOB104_PASSWORD
CLAUDE_API_KEY
REPORT_EMAIL, EMAIL_PASSWORD
```

## Database Migration

**Required before deploying this branch.** This project has no migration framework — `init_db()` only calls `create_all()`, which never alters existing tables. The production RDS `job_applications` table was created before the `needs_review`/`reviewed` columns existed, and `main.py`/the API now read and write those columns.

Run this against production **before** deploying an image built from this branch:

```sql
ALTER TABLE job_applications
  ADD COLUMN needs_review BOOLEAN DEFAULT FALSE,
  ADD COLUMN reviewed BOOLEAN DEFAULT FALSE;
```

If this is skipped, every `session.commit()` in the apply loop will fail with `Unknown column 'needs_review'`, the per-site error handling in `main.py` will silently mark every site as failed, and the run will "succeed" with 0 applications — the report email will misleadingly blame the scrapers rather than the missing column.

## AWS deployment

Infrastructure lives in `deploy/`. Run scripts in this order on first setup:

```bash
export AWS_PROFILE=<your-profile>
bash deploy/iam_setup.sh
bash deploy/s3_setup.sh        
bash deploy/rds_setup.sh
bash deploy/ecs_setup.sh
bash deploy/eventbridge_setup.sh
```

Upload the 104 auth session:
```bash
aws s3 cp auth_104.json s3://<your-config-bucket>/auth_104.json
```

Build and push the Docker image:
```bash
docker build --platform linux/amd64 -t autojobber .
bash deploy/ecr_push.sh
```

Trigger a manual run:
```bash
bash deploy/run_task.sh
```

Update your local IP to connect to RDS from TablePlus:
```bash
bash deploy/update_rds_ip.sh
```

## Architecture

```
EventBridge Scheduler (daily)
        │
        ▼
ECS Fargate Task ◄── ECR (Docker image)
        │
        ├── S3 ──────── config.json, resume.pdf, auth_104.json
        ├── Secrets Manager ── credentials
        ├── RDS MySQL ── job_applications, run_log
        └── CloudWatch Logs ── /ecs/autojobber
                │
                ▼
          Gmail SMTP (daily report email)
```
