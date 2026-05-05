#!/bin/bash
set -e

AWS_REGION="us-east-1"
CLUSTER_NAME="autojobber"

source deploy/.deploy_vars

echo "==> Running ECS task..."
TASK_ARN=$(aws ecs run-task \
  --cluster $CLUSTER_NAME \
  --task-definition autojobber \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_ID],securityGroups=[$ECS_SG_ID],assignPublicIp=ENABLED}" \
  --region $AWS_REGION \
  --query "tasks[0].taskArn" \
  --output text)
echo "    Task ARN: $TASK_ARN"
echo ""
echo "==> Tailing logs (Ctrl+C to stop)..."
sleep 10
aws logs tail /ecs/autojobber --follow --region $AWS_REGION | grep --line-buffered -E "applying|result|reason|skipped|failed|applied|login|no apply btn|job page|collected|apply-related"
