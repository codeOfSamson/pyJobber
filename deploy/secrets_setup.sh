#!/bin/bash
set -e

AWS_REGION="us-east-1"
SECRET_NAME="autojobber/production"

# Load values from local .env
set -a; source .env; set +a

echo "==> Creating or updating secret: $SECRET_NAME"
aws secretsmanager create-secret \
  --name $SECRET_NAME \
  --description "AutoJobber production credentials" \
  --region $AWS_REGION \
  --secret-string "{
    \"cakeresume_email\": \"$CAKERESUME_EMAIL\",
    \"cakeresume_password\": \"$CAKERESUME_PASSWORD\",
    \"job104_email\": \"$JOB104_EMAIL\",
    \"job104_password\": \"$JOB104_PASSWORD\",
    \"claude_api_key\": \"$CLAUDE_API_KEY\",
    \"db_host\": \"FILL_IN_AFTER_RDS\",
    \"db_user\": \"autojobber\",
    \"db_password\": \"$DB_PASSWORD\",
    \"db_name\": \"autojobber\",
    \"report_email\": \"$REPORT_EMAIL\",
    \"email_password\": \"$EMAIL_PASSWORD\"
  }"

echo "==> Verifying keys stored..."
aws secretsmanager get-secret-value \
  --secret-id $SECRET_NAME \
  --region $AWS_REGION \
  --query SecretString \
  --output text | python3 -c "import sys,json; print(list(json.load(sys.stdin).keys()))"

echo "==> Done."
