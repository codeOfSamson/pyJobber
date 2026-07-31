#!/bin/bash
set -e

AWS_REGION="us-east-1"
CLUSTER_NAME="autojobber"
CONTAINER_NAME="autojobber"

[ -f deploy/.deploy_vars ] && source deploy/.deploy_vars

echo "==> Running smoke test (login + collect links only, no applying)..."
TASK_ARN=$(aws ecs run-task \
  --cluster $CLUSTER_NAME \
  --task-definition autojobber \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$SUBNET_ID],securityGroups=[$ECS_SG_ID],assignPublicIp=ENABLED}" \
  --overrides "{\"containerOverrides\":[{\"name\":\"$CONTAINER_NAME\",\"environment\":[{\"name\":\"SMOKE_TEST\",\"value\":\"1\"}]}]}" \
  --region $AWS_REGION \
  --query "tasks[0].taskArn" \
  --output text)
echo "    Task ARN: $TASK_ARN"

echo "==> Waiting for task to stop..."
aws ecs wait tasks-stopped --cluster $CLUSTER_NAME --tasks $TASK_ARN --region $AWS_REGION

EXIT_CODE=$(aws ecs describe-tasks \
  --cluster $CLUSTER_NAME \
  --tasks $TASK_ARN \
  --region $AWS_REGION \
  --query "tasks[0].containers[0].exitCode" \
  --output text)

echo "==> Recent logs:"
aws logs tail /ecs/autojobber --since 15m --region $AWS_REGION | grep -E "smoke-test|Traceback|Error" || true

if [ "$EXIT_CODE" != "0" ]; then
  echo "==> Smoke test FAILED (exit code $EXIT_CODE)"
  exit 1
fi

echo "==> Smoke test passed."
