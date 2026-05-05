#!/bin/bash
set -e

ACCOUNT_ID="381076011493"
AWS_REGION="us-east-1"
SECRET_NAME="autojobber/production"

# Load DB password from .env
set -a; source .env; set +a

echo "==> Getting default VPC..."
VPC_ID=$(aws ec2 describe-vpcs \
  --filters "Name=is-default,Values=true" \
  --query "Vpcs[0].VpcId" \
  --output text \
  --region $AWS_REGION)
echo "    VPC: $VPC_ID"

echo "==> Creating RDS security group..."
RDS_SG_ID=$(aws ec2 create-security-group \
  --group-name autojobber-rds-sg \
  --description "AutoJobber RDS MySQL access" \
  --vpc-id $VPC_ID \
  --region $AWS_REGION \
  --query GroupId \
  --output text)
echo "    RDS SG: $RDS_SG_ID"

echo "==> Getting your public IP..."
MY_IP=$(curl -s https://checkip.amazonaws.com)
echo "    Your IP: $MY_IP"

echo "==> Allowing your local machine to connect (temporary — for testing)..."
aws ec2 authorize-security-group-ingress \
  --group-id $RDS_SG_ID \
  --protocol tcp \
  --port 3306 \
  --cidr $MY_IP/32 \
  --region $AWS_REGION

echo "==> Creating RDS instance (this takes 5-10 minutes)..."
aws rds create-db-instance \
  --db-instance-identifier autojobber \
  --db-instance-class db.t3.micro \
  --engine mysql \
  --engine-version "8.0" \
  --master-username autojobber \
  --master-user-password "$DB_PASSWORD" \
  --allocated-storage 20 \
  --db-name autojobber \
  --vpc-security-group-ids $RDS_SG_ID \
  --publicly-accessible \
  --no-multi-az \
  --region $AWS_REGION \
  --no-cli-pager

echo "==> Waiting for RDS to be available..."
aws rds wait db-instance-available \
  --db-instance-identifier autojobber \
  --region $AWS_REGION
echo "    RDS is ready!"

echo "==> Getting DB hostname..."
DB_HOST=$(aws rds describe-db-instances \
  --db-instance-identifier autojobber \
  --query "DBInstances[0].Endpoint.Address" \
  --output text \
  --region $AWS_REGION)
echo "    DB Host: $DB_HOST"

echo "==> Updating secret with real DB host..."
CURRENT=$(aws secretsmanager get-secret-value \
  --secret-id $SECRET_NAME \
  --region $AWS_REGION \
  --query SecretString \
  --output text)
UPDATED=$(echo $CURRENT | python3 -c "import sys,json; d=json.load(sys.stdin); d['db_host']='$DB_HOST'; print(json.dumps(d))")
aws secretsmanager update-secret \
  --secret-id $SECRET_NAME \
  --region $AWS_REGION \
  --secret-string "$UPDATED"
echo "    Secret updated."

echo "==> Testing DB connection and initializing schema..."
ENV=production SECRET_NAME=$SECRET_NAME python3 -c "
from secrets.loader import load_secrets
from db.client import get_engine, init_db, get_session
from db.models import JobApplication
s = load_secrets()
url = f\"mysql+pymysql://{s['db_user']}:{s['db_password']}@{s['db_host']}/{s['db_name']}\"
print('  Connecting to:', s['db_host'])
engine = get_engine(url)
init_db(engine)
session = get_session(engine)
print('  Tables created. Rows:', session.query(JobApplication).count())
"

echo ""
echo "==> Saving RDS SG ID for later use by ECS script..."
echo "RDS_SG_ID=$RDS_SG_ID" >> deploy/.deploy_vars
echo "DB_HOST=$DB_HOST" >> deploy/.deploy_vars

echo "==> Done."
