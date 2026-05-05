# AutoJobber AWS Deployment — Design Spec

**Date:** 2026-04-24
**Status:** Approved
**Approach:** Incremental, CLI-first — each step verified before proceeding to the next

---

## Goal

Deploy the AutoJobber Docker container to AWS so it runs automatically on a daily cron schedule. The deployment should be observable (CloudWatch Logs), secure (Secrets Manager, IAM least-privilege), and incrementally testable — each AWS service is wired up and verified independently before adding the next layer.

---

## Why Incremental

The jump from local to cloud introduces multiple new failure surfaces simultaneously: secrets not wired up, container can't reach the DB, IAM permissions missing, networking blocked. By verifying each layer independently before adding the next, you know exactly which layer broke when something fails.

---

## Incremental Steps (in order)

```
Step 1: ECR            → push Docker image, confirm it's in the registry
Step 2: S3             → upload config.json + resume.pdf, confirm local app can read them
Step 3: Secrets Mgr    → store credentials, confirm local app can fetch them
Step 4: IAM            → create ECS task role with access to S3 + Secrets Mgr
Step 5: RDS MySQL      → create database, run schema init, confirm connection
Step 6: ECS Fargate    → run container, watch CloudWatch Logs for a real run
Step 7: EventBridge    → wire up daily cron trigger, test with manual fire
```

Steps 1–5 are tested **from your local machine** with `ENV=production` set. You talk directly to real AWS services without ECS in the picture yet. This means when ECS runs in Step 6, you've already ruled out S3, Secrets Manager, and RDS as failure sources.

---

## Services and Their Roles

| Service | Role in AutoJobber |
|---|---|
| **ECR** | Stores the Docker image. ECS pulls from here. |
| **S3** | Stores `config.json` (search terms, settings) and `resume.pdf`. App reads on startup. |
| **Secrets Manager** | Stores all credentials (site logins, Claude API key, DB password, email password). App fetches on startup. |
| **IAM** | Task execution role — grants the ECS container permission to read S3 and Secrets Manager. Least-privilege: only the specific bucket and secret ARNs. |
| **RDS MySQL** | Managed database for `job_applications` and `run_log` tables. |
| **ECS Fargate** | Runs the Docker container serverlessly — no EC2 to manage. CloudWatch Logs captures all output. |
| **EventBridge Scheduler** | Fires the ECS task once daily on a cron schedule. |
| **CloudWatch Logs** | Captures all container stdout/stderr. Primary observability tool. |

---

## How Services Connect

```
EventBridge Scheduler
        │  triggers
        ▼
ECS Fargate Task
        │  pulls image from
        ├──► ECR
        │  reads config from
        ├──► S3
        │  fetches secrets from
        ├──► Secrets Manager
        │  reads/writes
        ├──► RDS MySQL
        │  writes logs to
        └──► CloudWatch Logs
```

The ECS task role (IAM) is what allows the container to talk to S3, Secrets Manager, and RDS. Without it, those calls fail with `AccessDenied`.

---

## Observability Strategy

### During Steps 1–5 (local → cloud services)
- Run `python3 main.py` locally with `ENV=production` in `.env`
- Each service has a built-in verify command (e.g., `aws s3 ls`, `aws secretsmanager get-secret-value`)
- Errors appear directly in your terminal

### During Step 6 (ECS)
- CloudWatch Logs group: `/ecs/autojobber`
- Tail logs in real time: `aws logs tail /ecs/autojobber --follow`
- All `print()` statements in `main.py` appear here
- ECS task status visible via `aws ecs describe-tasks`

### During Step 7 (EventBridge)
- Use "Test" trigger in EventBridge console or `aws scheduler create-schedule` with `--schedule-expression "rate(1 minute)"` for a quick test, then switch to the real daily cron

---

## IAM Permissions (least-privilege)

The ECS task role needs:
```json
{
  "s3:GetObject": "arn:aws:s3:::autojobber-config/*",
  "secretsmanager:GetSecretValue": "arn:aws:secretsmanager:REGION:ACCOUNT:secret:autojobber/*"
}
```

The ECS **task execution role** (separate from task role) needs:
- `AmazonECSTaskExecutionRolePolicy` (managed policy) — allows ECS to pull the image from ECR and push logs to CloudWatch

---

## Secrets Manager Structure

One secret named `autojobber/production` with a JSON value:
```json
{
  "cakeresume_email": "...",
  "cakeresume_password": "...",
  "job104_email": "...",
  "job104_password": "...",
  "claude_api_key": "...",
  "db_host": "...",
  "db_user": "...",
  "db_password": "...",
  "db_name": "autojobber",
  "report_email": "...",
  "email_password": "..."
}
```

The `secrets/loader.py` already reads `SECRET_NAME` from the environment and fetches this entire JSON blob when `ENV=production`.

---

## S3 Bucket Structure

Bucket name: `autojobber-config` (or similar — must be globally unique)

```
autojobber-config/
├── config.json       ← search terms, site settings
└── resume.pdf        ← your resume
```

`config/loader.py` reads `CONFIG_BUCKET` env var for the bucket name.
`main.py` reads `CONFIG_BUCKET` to download `resume.pdf` to `/tmp/resume.pdf`.

---

## RDS Configuration

- Engine: MySQL 8
- Instance class: `db.t3.micro` (cheapest, fine for a daily batch job)
- Storage: 20 GB gp2
- Publicly accessible: **No** — only reachable from within the VPC
- Security group: allow inbound 3306 from the ECS task security group only

Database name: `autojobber`
Schema is auto-created by SQLAlchemy `init_db()` on first run.

---

## ECS Task Definition Key Settings

- Launch type: Fargate
- CPU: 1 vCPU, Memory: 2 GB (Playwright/Chromium needs headroom)
- Container image: `ACCOUNT.dkr.ecr.REGION.amazonaws.com/autojobber:latest`
- Environment variables:
  - `ENV=production`
  - `SECRET_NAME=autojobber/production`
  - `CONFIG_BUCKET=autojobber-config`
- Log driver: `awslogs` → `/ecs/autojobber`
- Task role: the IAM role with S3 + Secrets Manager access

---

## EventBridge Schedule

- Schedule: `cron(0 1 * * ? *)` — 1:00 AM UTC daily (adjust for your timezone)
- Target: ECS task in the Fargate cluster
- Input: default (no custom input needed)

---

## Cost Estimate (rough)

| Service | Monthly cost |
|---|---|
| ECS Fargate (1 vCPU, 2GB, ~15min/day) | ~$1–2 |
| RDS db.t3.micro | ~$15 |
| S3 | <$1 |
| Secrets Manager | ~$0.40/secret |
| ECR | ~$0.10 |
| **Total** | **~$18–20/month** |

RDS dominates the cost. Could use a local SQLite or DynamoDB to reduce cost — but MySQL keeps the design closest to the existing code.

---

## Out of Scope

- VPC creation (will use the default VPC)
- CI/CD pipeline (image build + push is manual for now)
- Multi-region deployment
- Auto-scaling
