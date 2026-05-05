# AWS Deployment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy AutoJobber to AWS ECS Fargate with full observability, running automatically on a daily cron schedule.

**Architecture:** Incremental CLI-first setup — each AWS service is wired up and verified from the local machine before ECS is involved. Steps 1–5 test real AWS services locally (ENV=production), Step 6 hands off to ECS, Step 7 automates with EventBridge.

**Tech Stack:** AWS CLI, Docker, ECR, S3, Secrets Manager, IAM, RDS MySQL, ECS Fargate, EventBridge, CloudWatch Logs

---

## Prerequisites

Before starting, run these to confirm your environment is ready:

```bash
aws sts get-caller-identity        # confirms AWS CLI is authenticated
docker --version                   # confirms Docker is installed
python3 --version                  # confirms Python 3 available
```

Then set these shell variables — you'll use them throughout every step:

```bash
export AWS_REGION="ap-northeast-1"          # Tokyo — change if preferred
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export BUCKET_NAME="autojobber-config-${ACCOUNT_ID}"   # globally unique
export SECRET_NAME="autojobber/production"
export ECR_REPO="autojobber"
export CLUSTER_NAME="autojobber"
echo "Account: $ACCOUNT_ID  Region: $AWS_REGION"
```

> **Why these variables?** AWS resource names (bucket names, ARNs, image URLs) embed your account ID and region. Setting them once as variables means you can copy-paste every command in this plan without editing.

---

## Task 1: Fix Headless Mode for Docker

**Why:** `browser.py` currently launches Chromium with `headless=False` (for local debugging). Inside a Docker container there's no display — Chromium will crash immediately. We also need `--no-sandbox` because Docker containers typically run as root, which Chromium refuses without it.

**Files:**
- Modify: `browser/browser.py`

- [ ] **Step 1: Update `create_browser` to use headless mode in production**

Replace the function in `browser/browser.py`:

```python
import os
import random
import time
from playwright.sync_api import Browser, BrowserContext, Page

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]


def create_browser(playwright) -> Browser:
    production = os.environ.get("ENV") == "production"
    args = ["--no-sandbox", "--disable-dev-shm-usage"] if production else []
    return playwright.chromium.launch(headless=production, args=args)


def create_page(browser: Browser) -> Page:
    context: BrowserContext = browser.new_context(
        user_agent=random.choice(USER_AGENTS),
        viewport={"width": 1280, "height": 800},
    )
    return context.new_page()


def human_delay(min_s: float = 1.0, max_s: float = 3.0) -> None:
    time.sleep(random.uniform(min_s, max_s))
```

- [ ] **Step 2: Verify the change is correct**

```bash
grep "headless" browser/browser.py
```

Expected output:
```
    return playwright.chromium.launch(headless=production, args=args)
```

- [ ] **Step 3: Commit**

```bash
git add browser/browser.py
git commit -m "fix: headless mode and --no-sandbox for Docker/ECS production"
```

---

## Task 2: ECR — Push Docker Image

**Why:** ECS pulls the Docker image from ECR (AWS's private container registry). You push once here; every future ECS run pulls this image. Think of ECR like a private Docker Hub.

**Files:** No code changes — AWS CLI + Docker commands only.

- [ ] **Step 1: Create the ECR repository**

```bash
aws ecr create-repository \
  --repository-name $ECR_REPO \
  --region $AWS_REGION
```

Expected output: JSON with `"repositoryUri"` — note this URI, it's where you push the image.

- [ ] **Step 2: Authenticate Docker to ECR**

```bash
aws ecr get-login-password --region $AWS_REGION \
  | docker login --username AWS --password-stdin \
    $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com
```

Expected output: `Login Succeeded`

> **Why this works:** ECR uses temporary tokens (12h expiry) instead of passwords. `get-login-password` fetches the token; `docker login` saves it so Docker can push.

- [ ] **Step 3: Build the image**

```bash
docker build -t $ECR_REPO .
```

Expected: build completes, final line is `Successfully tagged autojobber:latest` (or similar).

- [ ] **Step 4: Tag and push**

```bash
docker tag $ECR_REPO:latest \
  $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest

docker push \
  $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest
```

Expected: progress bars, ends with `latest: digest: sha256:...`

- [ ] **Step 5: Verify the image is in ECR**

```bash
aws ecr list-images \
  --repository-name $ECR_REPO \
  --region $AWS_REGION
```

Expected output includes `"imageTag": "latest"`. ✓

- [ ] **Step 6: Commit nothing** (no code changed — just note the image URI for later)

```bash
echo "Image URI: $ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest"
```

---

## Task 3: S3 — Config and Resume

**Why:** In production, `config/loader.py` reads `config.json` from S3 instead of local disk. `main.py` downloads `resume.pdf` from S3 to `/tmp/`. We verify this works locally before ECS is involved.

- [ ] **Step 1: Create the S3 bucket**

```bash
aws s3api create-bucket \
  --bucket $BUCKET_NAME \
  --region $AWS_REGION \
  --create-bucket-configuration LocationConstraint=$AWS_REGION
```

Expected: `{"Location": "http://autojobber-config-ACCOUNT.s3.amazonaws.com/"}`

> **Note:** `us-east-1` doesn't need `--create-bucket-configuration`. All other regions do. This command handles all regions.

- [ ] **Step 2: Block all public access (security best practice)**

```bash
aws s3api put-public-access-block \
  --bucket $BUCKET_NAME \
  --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
```

No output = success.

- [ ] **Step 3: Upload config.json**

```bash
aws s3 cp config.json s3://$BUCKET_NAME/config.json
```

Expected: `upload: ./config.json to s3://autojobber-config-ACCOUNT/config.json`

- [ ] **Step 4: Upload resume.pdf**

```bash
aws s3 cp resume.pdf s3://$BUCKET_NAME/resume.pdf
```

Expected: `upload: ./resume.pdf to s3://autojobber-config-ACCOUNT/resume.pdf`

- [ ] **Step 5: Verify both files are there**

```bash
aws s3 ls s3://$BUCKET_NAME/
```

Expected:
```
YYYY-MM-DD HH:MM:SS   NNNN config.json
YYYY-MM-DD HH:MM:SS   NNNN resume.pdf
```

- [ ] **Step 6: Test the app can read config from S3**

Temporarily add to your `.env`:
```
ENV=production
CONFIG_BUCKET=autojobber-config-ACCOUNT_ID_HERE
```

Then:
```bash
python3 -c "
from config.loader import load_config
cfg = load_config()
print('search_terms:', cfg['search_terms'])
print('sites:', cfg['sites'])
"
```

Expected: prints your search terms and sites from the S3 config. If you get `AccessDenied`, your local AWS credentials don't have S3 read access — add `AmazonS3ReadOnlyAccess` to your IAM user temporarily.

- [ ] **Step 7: Revert ENV in .env back to local**

Change `.env` back:
```
ENV=local
```

---

## Task 4: Secrets Manager — Store Credentials

**Why:** In production, `secrets/loader.py` fetches one JSON blob from Secrets Manager instead of reading from `.env`. All credentials (site logins, API keys, DB password) live in one secret. The app never has credentials baked into the image.

- [ ] **Step 1: Build the secret JSON from your .env values**

Create a file `secret.json` (do NOT commit this):
```json
{
  "cakeresume_email": "YOUR_CAKERESUME_EMAIL",
  "cakeresume_password": "YOUR_CAKERESUME_PASSWORD",
  "job104_email": "YOUR_JOB104_EMAIL",
  "job104_password": "YOUR_JOB104_PASSWORD",
  "claude_api_key": "YOUR_CLAUDE_API_KEY",
  "db_host": "PLACEHOLDER_FILL_AFTER_RDS",
  "db_user": "autojobber",
  "db_password": "CHOOSE_A_STRONG_PASSWORD",
  "db_name": "autojobber",
  "report_email": "YOUR_GMAIL",
  "email_password": "YOUR_GMAIL_APP_PASSWORD"
}
```

> `db_host` is a placeholder — you'll update it after RDS is created in Task 6.

- [ ] **Step 2: Create the secret**

```bash
aws secretsmanager create-secret \
  --name $SECRET_NAME \
  --description "AutoJobber production credentials" \
  --secret-string file://secret.json \
  --region $AWS_REGION
```

Expected: JSON with `"ARN"` and `"Name": "autojobber/production"`.

- [ ] **Step 3: Verify the secret was stored**

```bash
aws secretsmanager get-secret-value \
  --secret-id $SECRET_NAME \
  --region $AWS_REGION \
  --query SecretString \
  --output text | python3 -m json.tool
```

Expected: your JSON printed formatted. Confirm the keys are all there.

- [ ] **Step 4: Test the app can fetch secrets**

Add to `.env`:
```
ENV=production
SECRET_NAME=autojobber/production
CONFIG_BUCKET=autojobber-config-ACCOUNT_ID_HERE
```

Then:
```bash
python3 -c "
from secrets.loader import load_secrets
s = load_secrets()
print('keys:', list(s.keys()))
print('email:', s['cakeresume_email'])
"
```

Expected: prints all 11 keys and your CakeResume email. If `AccessDenied`, add `SecretsManagerReadWrite` to your IAM user temporarily.

- [ ] **Step 5: Delete the local secret.json**

```bash
rm secret.json
```

> Never leave credentials in plaintext files.

- [ ] **Step 6: Revert .env back to local**

```
ENV=local
```

---

## Task 5: IAM — Task Role and Execution Role

**Why:** ECS needs two IAM roles:
- **Task Role** — what the *app code* is allowed to do (read S3, read Secrets Manager)
- **Task Execution Role** — what *ECS itself* is allowed to do (pull the Docker image from ECR, write logs to CloudWatch)

These are separate because the app code shouldn't need ECR/CloudWatch permissions, and ECS infrastructure shouldn't need your app's S3/secrets.

- [ ] **Step 1: Create the trust policy file for ECS tasks**

Create `ecs-trust-policy.json`:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
```

> **What this means:** "ECS tasks are allowed to assume (use) this role." Without this trust policy, even if the role has permissions, ECS can't use it.

- [ ] **Step 2: Create the Task Role**

```bash
aws iam create-role \
  --role-name autojobber-task-role \
  --assume-role-policy-document file://ecs-trust-policy.json
```

Expected: JSON with `"RoleName": "autojobber-task-role"` and an ARN. Note the ARN.

- [ ] **Step 3: Create the app permissions policy file**

Create `task-policy.json` (replace REGION and ACCOUNT_ID):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::autojobber-config-ACCOUNT_ID/*"
    },
    {
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": "arn:aws:secretsmanager:REGION:ACCOUNT_ID:secret:autojobber/*"
    }
  ]
}
```

> **Why least-privilege?** The role can only read from this specific S3 bucket and this specific secret. If the container is compromised, it can't read other S3 buckets or other secrets in your account.

- [ ] **Step 4: Attach the policy to the Task Role**

```bash
aws iam put-role-policy \
  --role-name autojobber-task-role \
  --policy-name autojobber-task-policy \
  --policy-document file://task-policy.json
```

No output = success.

- [ ] **Step 5: Create the Task Execution Role**

```bash
aws iam create-role \
  --role-name autojobber-execution-role \
  --assume-role-policy-document file://ecs-trust-policy.json
```

- [ ] **Step 6: Attach the managed execution policy**

```bash
aws iam attach-role-policy \
  --role-name autojobber-execution-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
```

No output = success. This policy lets ECS pull from ECR and write to CloudWatch.

- [ ] **Step 7: Verify both roles exist**

```bash
aws iam get-role --role-name autojobber-task-role --query Role.Arn --output text
aws iam get-role --role-name autojobber-execution-role --query Role.Arn --output text
```

Expected: two ARNs printed. Note both — you'll use them in the ECS task definition.

- [ ] **Step 8: Clean up temp files**

```bash
rm ecs-trust-policy.json task-policy.json
```

---

## Task 6: RDS MySQL — Create the Database

**Why:** AutoJobber stores `job_applications` and `run_log` in MySQL. RDS is a managed MySQL service — AWS handles backups, patching, and availability. SQLAlchemy's `init_db()` creates the tables on first connection.

- [ ] **Step 1: Get your public IP (needed to connect from local for testing)**

```bash
curl -s https://checkip.amazonaws.com
```

Note this IP — you'll allow it to reach RDS temporarily.

- [ ] **Step 2: Create a security group for RDS**

```bash
# Get the default VPC ID
VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=is-default,Values=true" \
  --query "Vpcs[0].VpcId" \
  --output text \
  --region $AWS_REGION)
echo "Default VPC: $VPC_ID"

# Create security group
RDS_SG_ID=$(aws ec2 create-security-group \
  --group-name autojobber-rds-sg \
  --description "AutoJobber RDS MySQL access" \
  --vpc-id $VPC_ID \
  --region $AWS_REGION \
  --query GroupId \
  --output text)
echo "RDS Security Group: $RDS_SG_ID"
```

- [ ] **Step 3: Allow inbound MySQL from your local IP (temporary)**

Replace `YOUR_PUBLIC_IP` with the IP from Step 1:
```bash
aws ec2 authorize-security-group-ingress \
  --group-id $RDS_SG_ID \
  --protocol tcp \
  --port 3306 \
  --cidr YOUR_PUBLIC_IP/32 \
  --region $AWS_REGION
```

> This is temporary — for testing the connection from your laptop. You'll remove it after Step 5.

- [ ] **Step 4: Create the RDS instance**

This takes 5–10 minutes. Use the DB password you put in Secrets Manager:

```bash
aws rds create-db-instance \
  --db-instance-identifier autojobber \
  --db-instance-class db.t3.micro \
  --engine mysql \
  --engine-version "8.0" \
  --master-username autojobber \
  --master-user-password "YOUR_DB_PASSWORD_FROM_SECRET" \
  --allocated-storage 20 \
  --db-name autojobber \
  --vpc-security-group-ids $RDS_SG_ID \
  --publicly-accessible \
  --no-multi-az \
  --region $AWS_REGION
```

Expected: large JSON response with `"DBInstanceStatus": "creating"`.

- [ ] **Step 5: Wait for RDS to be available**

```bash
aws rds wait db-instance-available \
  --db-instance-identifier autojobber \
  --region $AWS_REGION
echo "RDS is ready"
```

This command blocks until RDS is ready (5–10 min). When it prints "RDS is ready", continue.

- [ ] **Step 6: Get the RDS hostname**

```bash
DB_HOST=$(aws rds describe-db-instances \
  --db-instance-identifier autojobber \
  --query "DBInstances[0].Endpoint.Address" \
  --output text \
  --region $AWS_REGION)
echo "DB Host: $DB_HOST"
```

- [ ] **Step 7: Update the secret with the real DB host**

```bash
aws secretsmanager update-secret \
  --secret-id $SECRET_NAME \
  --region $AWS_REGION \
  --secret-string "{
    \"cakeresume_email\": \"$(aws secretsmanager get-secret-value --secret-id $SECRET_NAME --region $AWS_REGION --query SecretString --output text | python3 -c \"import sys,json; d=json.load(sys.stdin); print(d['cakeresume_email'])\")\"
  }"
```

Actually this is complex to do inline. Instead, fetch the secret, edit the db_host, re-upload:

```bash
# Fetch current secret to a temp file
aws secretsmanager get-secret-value \
  --secret-id $SECRET_NAME \
  --region $AWS_REGION \
  --query SecretString \
  --output text > /tmp/secret_update.json

# Edit /tmp/secret_update.json — update "db_host" to $DB_HOST value
# Open in your editor:
open /tmp/secret_update.json   # or: nano /tmp/secret_update.json

# Re-upload
aws secretsmanager update-secret \
  --secret-id $SECRET_NAME \
  --region $AWS_REGION \
  --secret-string file:///tmp/secret_update.json

# Delete the temp file
rm /tmp/secret_update.json
```

- [ ] **Step 8: Test the connection and initialize the schema**

Add to `.env`:
```
ENV=production
SECRET_NAME=autojobber/production
CONFIG_BUCKET=autojobber-config-ACCOUNT_ID_HERE
```

```bash
python3 -c "
from secrets.loader import load_secrets
from db.client import get_engine, init_db, get_session

secrets = load_secrets()
db_url = f\"mysql+pymysql://{secrets['db_user']}:{secrets['db_password']}@{secrets['db_host']}/{secrets['db_name']}\"
print('Connecting to:', secrets['db_host'])
engine = get_engine(db_url)
init_db(engine)
print('Schema initialized successfully')
session = get_session(engine)
from db.models import JobApplication
count = session.query(JobApplication).count()
print(f'job_applications rows: {count}')
"
```

Expected:
```
Connecting to: autojobber.xxxxx.ap-northeast-1.rds.amazonaws.com
Schema initialized successfully
job_applications rows: 0
```

- [ ] **Step 9: Lock down RDS — remove public IP access**

```bash
# Remove your local IP from the RDS security group
aws ec2 revoke-security-group-ingress \
  --group-id $RDS_SG_ID \
  --protocol tcp \
  --port 3306 \
  --cidr YOUR_PUBLIC_IP/32 \
  --region $AWS_REGION

# Disable public accessibility on RDS
aws rds modify-db-instance \
  --db-instance-identifier autojobber \
  --no-publicly-accessible \
  --apply-immediately \
  --region $AWS_REGION
```

> From this point RDS is only reachable from within the VPC (where ECS tasks run).

- [ ] **Step 10: Revert .env back to local**

```
ENV=local
```

---

## Task 7: ECS Fargate — Run the Container

**Why:** This is the payoff step — the container runs in the cloud with all the services wired together. CloudWatch Logs is your window into what's happening.

- [ ] **Step 1: Create a CloudWatch log group**

```bash
aws logs create-log-group \
  --log-group-name /ecs/autojobber \
  --region $AWS_REGION
```

No output = success. This is where all `print()` output from the container will appear.

- [ ] **Step 2: Create the ECS cluster**

```bash
aws ecs create-cluster \
  --cluster-name $CLUSTER_NAME \
  --region $AWS_REGION
```

Expected: JSON with `"clusterName": "autojobber"` and `"status": "ACTIVE"`.

> **What's a cluster?** Just a logical grouping for your tasks. Fargate clusters have no servers — tasks spin up on AWS-managed infrastructure.

- [ ] **Step 3: Create the ECS security group**

```bash
ECS_SG_ID=$(aws ec2 create-security-group \
  --group-name autojobber-ecs-sg \
  --description "AutoJobber ECS tasks" \
  --vpc-id $VPC_ID \
  --region $AWS_REGION \
  --query GroupId \
  --output text)
echo "ECS Security Group: $ECS_SG_ID"
```

- [ ] **Step 4: Allow ECS tasks to reach RDS**

```bash
aws ec2 authorize-security-group-ingress \
  --group-id $RDS_SG_ID \
  --protocol tcp \
  --port 3306 \
  --source-group $ECS_SG_ID \
  --region $AWS_REGION
```

> This says: "Allow inbound MySQL connections from the ECS security group." RDS stays private — only ECS tasks can reach it.

- [ ] **Step 5: Get the task role ARNs**

```bash
TASK_ROLE_ARN=$(aws iam get-role --role-name autojobber-task-role --query Role.Arn --output text)
EXEC_ROLE_ARN=$(aws iam get-role --role-name autojobber-execution-role --query Role.Arn --output text)
echo "Task role: $TASK_ROLE_ARN"
echo "Exec role: $EXEC_ROLE_ARN"
```

- [ ] **Step 6: Create the task definition JSON**

Create `task-def.json` (replace all CAPS placeholders):

```json
{
  "family": "autojobber",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "taskRoleArn": "TASK_ROLE_ARN",
  "executionRoleArn": "EXEC_ROLE_ARN",
  "containerDefinitions": [
    {
      "name": "autojobber",
      "image": "ACCOUNT_ID.dkr.ecr.REGION.amazonaws.com/autojobber:latest",
      "essential": true,
      "environment": [
        {"name": "ENV", "value": "production"},
        {"name": "SECRET_NAME", "value": "autojobber/production"},
        {"name": "CONFIG_BUCKET", "value": "BUCKET_NAME"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/autojobber",
          "awslogs-region": "REGION",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

You can generate this with your shell variables:
```bash
cat > task-def.json << EOF
{
  "family": "autojobber",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "taskRoleArn": "$TASK_ROLE_ARN",
  "executionRoleArn": "$EXEC_ROLE_ARN",
  "containerDefinitions": [
    {
      "name": "autojobber",
      "image": "$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO:latest",
      "essential": true,
      "environment": [
        {"name": "ENV", "value": "production"},
        {"name": "SECRET_NAME", "value": "$SECRET_NAME"},
        {"name": "CONFIG_BUCKET", "value": "$BUCKET_NAME"}
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/autojobber",
          "awslogs-region": "$AWS_REGION",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
EOF
cat task-def.json   # review before registering
```

- [ ] **Step 7: Register the task definition**

```bash
aws ecs register-task-definition \
  --cli-input-json file://task-def.json \
  --region $AWS_REGION
```

Expected: JSON with `"taskDefinitionArn"` ending in `:1`.

- [ ] **Step 8: Get a subnet ID from the default VPC**

```bash
SUBNET_ID=$(aws ec2 describe-subnets \
  --filters "Name=vpc-id,Values=$VPC_ID" \
  --query "Subnets[0].SubnetId" \
  --output text \
  --region $AWS_REGION)
echo "Subnet: $SUBNET_ID"
```

- [ ] **Step 9: Run the task manually**

```bash
TASK_ARN=$(aws ecs run-task \
  --cluster $CLUSTER_NAME \
  --task-definition autojobber \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_ID],securityGroups=[$ECS_SG_ID],assignPublicIp=ENABLED}" \
  --region $AWS_REGION \
  --query "tasks[0].taskArn" \
  --output text)
echo "Task ARN: $TASK_ARN"
```

> `assignPublicIp=ENABLED` — Fargate tasks in a public subnet need a public IP to pull from ECR. Without it, the image pull fails with a network error.

- [ ] **Step 10: Watch the logs in real time**

```bash
aws logs tail /ecs/autojobber --follow --region $AWS_REGION
```

You should see the bot starting up, logging in, searching for jobs. Press Ctrl+C to stop tailing.

If the task fails immediately, check the task status for the stop reason:
```bash
aws ecs describe-tasks \
  --cluster $CLUSTER_NAME \
  --tasks $TASK_ARN \
  --region $AWS_REGION \
  --query "tasks[0].{status:lastStatus,stopped:stoppedReason,containers:containers[0].reason}"
```

- [ ] **Step 11: Clean up temp file**

```bash
rm task-def.json
```

---

## Task 8: EventBridge — Daily Cron Trigger

**Why:** Instead of running the task manually, EventBridge fires it automatically every day. It needs its own IAM role to call ECS on your behalf.

- [ ] **Step 1: Create the EventBridge trust policy**

```bash
cat > eventbridge-trust.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"Service": "scheduler.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
```

- [ ] **Step 2: Create the EventBridge role**

```bash
aws iam create-role \
  --role-name autojobber-scheduler-role \
  --assume-role-policy-document file://eventbridge-trust.json
```

- [ ] **Step 3: Create the ECS run policy for EventBridge**

```bash
cat > eventbridge-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "ecs:RunTask",
      "Resource": "arn:aws:ecs:$AWS_REGION:$ACCOUNT_ID:task-definition/autojobber:*"
    },
    {
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": [
        "$TASK_ROLE_ARN",
        "$EXEC_ROLE_ARN"
      ]
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name autojobber-scheduler-role \
  --policy-name autojobber-scheduler-policy \
  --policy-document file://eventbridge-policy.json
```

> `iam:PassRole` is required — EventBridge must "pass" the task role and execution role to ECS when launching the task.

- [ ] **Step 4: Get the scheduler role ARN**

```bash
SCHEDULER_ROLE_ARN=$(aws iam get-role \
  --role-name autojobber-scheduler-role \
  --query Role.Arn \
  --output text)
echo "Scheduler role: $SCHEDULER_ROLE_ARN"
```

- [ ] **Step 5: Create the ECS target JSON**

```bash
cat > ecs-target.json << EOF
{
  "TaskDefinitionArn": "arn:aws:ecs:$AWS_REGION:$ACCOUNT_ID:task-definition/autojobber",
  "LaunchType": "FARGATE",
  "NetworkConfiguration": {
    "AwsvpcConfiguration": {
      "Subnets": ["$SUBNET_ID"],
      "SecurityGroups": ["$ECS_SG_ID"],
      "AssignPublicIp": "ENABLED"
    }
  }
}
EOF
```

- [ ] **Step 6: Create the schedule (1:00 AM UTC daily)**

```bash
aws scheduler create-schedule \
  --name autojobber-daily \
  --schedule-expression "cron(0 1 * * ? *)" \
  --flexible-time-window Mode=OFF \
  --target "{
    \"Arn\": \"arn:aws:ecs:$AWS_REGION:$ACCOUNT_ID:cluster/$CLUSTER_NAME\",
    \"RoleArn\": \"$SCHEDULER_ROLE_ARN\",
    \"EcsParameters\": $(cat ecs-target.json)
  }" \
  --region $AWS_REGION
```

Expected: JSON with `"ScheduleArn"`.

> **Adjust the time:** `cron(0 1 * * ? *)` = 1:00 AM UTC. For Taiwan (UTC+8), that's 9:00 AM local time. To change to midnight Taiwan time (4 PM UTC): `cron(0 16 * * ? *)`.

- [ ] **Step 7: Test with a one-time manual trigger**

```bash
aws scheduler create-schedule \
  --name autojobber-test-once \
  --schedule-expression "at($(date -u -v+2M +%Y-%m-%dT%H:%M:%S))" \
  --flexible-time-window Mode=OFF \
  --target "{
    \"Arn\": \"arn:aws:ecs:$AWS_REGION:$ACCOUNT_ID:cluster/$CLUSTER_NAME\",
    \"RoleArn\": \"$SCHEDULER_ROLE_ARN\",
    \"EcsParameters\": $(cat ecs-target.json)
  }" \
  --region $AWS_REGION
```

Then watch logs:
```bash
aws logs tail /ecs/autojobber --follow --region $AWS_REGION
```

The task should start within 2 minutes.

- [ ] **Step 8: Delete the test schedule after confirming it works**

```bash
aws scheduler delete-schedule --name autojobber-test-once --region $AWS_REGION
```

- [ ] **Step 9: Clean up temp files**

```bash
rm eventbridge-trust.json eventbridge-policy.json ecs-target.json
```

- [ ] **Step 10: Commit nothing** (all changes are in AWS — no code modified)

---

## Verification Checklist

After all tasks complete, confirm:

- [ ] `aws ecr list-images --repository-name autojobber` shows `latest` tag
- [ ] `aws s3 ls s3://$BUCKET_NAME/` shows `config.json` and `resume.pdf`
- [ ] `aws secretsmanager get-secret-value --secret-id $SECRET_NAME` returns all 11 keys including real `db_host`
- [ ] `aws iam get-role --role-name autojobber-task-role` returns a role with S3 + Secrets Manager policy
- [ ] `aws rds describe-db-instances --db-instance-identifier autojobber` shows `"DBInstanceStatus": "available"`
- [ ] `aws logs tail /ecs/autojobber` shows a completed run with applied/skipped/failed counts
- [ ] `aws scheduler get-schedule --name autojobber-daily` shows the daily cron is active

---

## Troubleshooting Reference

| Symptom | Likely cause | Fix |
|---|---|---|
| Task stops immediately, `CannotPullContainerError` | ECR auth / no public IP | Check `assignPublicIp=ENABLED`, re-run ECR login |
| `AccessDenied` on S3 | Task role missing S3 policy | Re-check Task 5 Step 4 |
| `AccessDenied` on Secrets Manager | Task role missing SM policy | Re-check Task 5 Step 4 |
| `Can't connect to MySQL` | RDS security group | Check ECS SG is allowed inbound on RDS SG |
| Container exits with `playwright._impl._errors.Error` | Missing `--no-sandbox` | Verify Task 1 code change is in the pushed image |
| No logs in CloudWatch | Execution role missing policy | Re-check Task 5 Step 6 |
