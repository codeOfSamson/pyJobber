#!/bin/bash
set -e

ACCOUNT_ID="381076011493"
AWS_REGION="us-east-1"
BUCKET_NAME="autojobber-config-$ACCOUNT_ID"
SECRET_PREFIX="arn:aws:secretsmanager:$AWS_REGION:$ACCOUNT_ID:secret:autojobber/*"

echo "==> Creating trust policy (allows ECS tasks to assume these roles)..."
cat > /tmp/ecs-trust.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "ecs-tasks.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
EOF

echo "==> Creating Task Role (what the app code is allowed to do)..."
aws iam create-role \
  --role-name autojobber-task-role \
  --assume-role-policy-document file:///tmp/ecs-trust.json

cat > /tmp/task-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::$BUCKET_NAME/*"
    },
    {
      "Effect": "Allow",
      "Action": "secretsmanager:GetSecretValue",
      "Resource": "$SECRET_PREFIX"
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name autojobber-task-role \
  --policy-name autojobber-task-policy \
  --policy-document file:///tmp/task-policy.json

echo "==> Creating Execution Role (what ECS itself is allowed to do)..."
aws iam create-role \
  --role-name autojobber-execution-role \
  --assume-role-policy-document file:///tmp/ecs-trust.json

aws iam attach-role-policy \
  --role-name autojobber-execution-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

echo "==> Verifying roles..."
aws iam get-role --role-name autojobber-task-role --query Role.Arn --output text
aws iam get-role --role-name autojobber-execution-role --query Role.Arn --output text

rm /tmp/ecs-trust.json /tmp/task-policy.json
echo "==> Done."
