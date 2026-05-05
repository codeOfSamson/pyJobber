#!/bin/bash
set -e

ACCOUNT_ID="381076011493"
AWS_REGION="us-east-1"
CLUSTER_NAME="autojobber"

source deploy/.deploy_vars

export AWS_PROFILE=personal

echo "==> Getting IAM role ARNs..."
TASK_ROLE_ARN=$(aws iam get-role --role-name autojobber-task-role --query Role.Arn --output text --region $AWS_REGION)
EXEC_ROLE_ARN=$(aws iam get-role --role-name autojobber-execution-role --query Role.Arn --output text --region $AWS_REGION)

echo "==> Creating EventBridge IAM role for ECS..."
cat > /tmp/eb-trust.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "scheduler.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
EOF

SCHED_ROLE_ARN=$(aws iam create-role \
  --role-name autojobber-scheduler-role \
  --assume-role-policy-document file:///tmp/eb-trust.json \
  --query Role.Arn --output text 2>/dev/null || \
  aws iam get-role --role-name autojobber-scheduler-role --query Role.Arn --output text)
echo "    Scheduler role: $SCHED_ROLE_ARN"

aws iam attach-role-policy \
  --role-name autojobber-scheduler-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonECS_FullAccess 2>/dev/null || true

echo "==> Creating EventBridge schedule (daily 10:47 AM Taiwan = 02:47 UTC)..."
aws scheduler create-schedule \
  --name autojobber-daily \
  --schedule-expression "cron(47 2 * * ? *)" \
  --schedule-expression-timezone "Asia/Taipei" \
  --flexible-time-window '{"Mode": "FLEXIBLE", "MaximumWindowInMinutes": 30}' \
  --target "{
    \"Arn\": \"arn:aws:ecs:$AWS_REGION:$ACCOUNT_ID:cluster/$CLUSTER_NAME\",
    \"RoleArn\": \"$SCHED_ROLE_ARN\",
    \"EcsParameters\": {
      \"TaskDefinitionArn\": \"arn:aws:ecs:$AWS_REGION:$ACCOUNT_ID:task-definition/autojobber\",
      \"LaunchType\": \"FARGATE\",
      \"NetworkConfiguration\": {
        \"awsvpcConfiguration\": {
          \"Subnets\": [\"$SUBNET_ID\"],
          \"SecurityGroups\": [\"$ECS_SG_ID\"],
          \"AssignPublicIp\": \"ENABLED\"
        }
      }
    }
  }" \
  --region $AWS_REGION \
  --no-cli-pager

echo ""
echo "==> Done. Autojobber will run daily between 10:47-11:17 AM Taiwan time."
