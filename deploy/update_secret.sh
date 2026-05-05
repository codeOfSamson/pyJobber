#!/bin/bash
set -e

AWS_REGION="us-east-1"
SECRET_NAME="autojobber/production"

set -a; source .env; set +a

echo "==> Fetching current secret..."
CURRENT=$(aws secretsmanager get-secret-value \
  --secret-id $SECRET_NAME \
  --region $AWS_REGION \
  --query SecretString \
  --output text)

echo "==> Updating with latest .env values..."
UPDATED=$(echo $CURRENT | python3 -c "
import sys, json, os
d = json.load(sys.stdin)
d['email_password'] = os.environ['EMAIL_PASSWORD']
d['report_email'] = os.environ['REPORT_EMAIL']
print(json.dumps(d))
")

aws secretsmanager update-secret \
  --secret-id $SECRET_NAME \
  --region $AWS_REGION \
  --secret-string "$UPDATED"

echo "==> Done. Verifying email_password is updated..."
aws secretsmanager get-secret-value \
  --secret-id $SECRET_NAME \
  --region $AWS_REGION \
  --query SecretString \
  --output text | python3 -c "import sys,json; d=json.load(sys.stdin); print('email_password length:', len(d['email_password']))"
