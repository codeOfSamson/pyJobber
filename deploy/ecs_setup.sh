#!/bin/bash
set -e

ACCOUNT_ID="381076011493"
AWS_REGION="us-east-1"
CLUSTER_NAME="autojobber"
SECRET_NAME="autojobber/production"
BUCKET_NAME="autojobber-config-$ACCOUNT_ID"
IMAGE="$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/autojobber:latest"

# Load vars saved by rds_setup.sh
source deploy/.deploy_vars

echo "==> Getting IAM role ARNs..."
TASK_ROLE_ARN=$(aws iam get-role --role-name autojobber-task-role --query Role.Arn --output text)
EXEC_ROLE_ARN=$(aws iam get-role --role-name autojobber-execution-role --query Role.Arn --output text)
echo "    Task role:      $TASK_ROLE_ARN"
echo "    Execution role: $EXEC_ROLE_ARN"

echo "==> Creating CloudWatch log group..."
aws logs create-log-group --log-group-name /ecs/autojobber --region $AWS_REGION || echo "    (already exists)"

echo "==> Creating ECS cluster..."
aws ecs create-cluster --cluster-name $CLUSTER_NAME --region $AWS_REGION --no-cli-pager

echo "==> Getting default VPC and subnet..."
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=is-default,Values=true" --query "Vpcs[0].VpcId" --output text --region $AWS_REGION)
SUBNET_ID=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=$VPC_ID" --query "Subnets[0].SubnetId" --output text --region $AWS_REGION)
echo "    VPC: $VPC_ID  Subnet: $SUBNET_ID"

echo "==> Creating ECS security group..."
ECS_SG_ID=$(aws ec2 create-security-group \
  --group-name autojobber-ecs-sg \
  --description "AutoJobber ECS tasks" \
  --vpc-id $VPC_ID \
  --region $AWS_REGION \
  --query GroupId \
  --output text)
echo "    ECS SG: $ECS_SG_ID"

echo "==> Allowing ECS tasks to reach RDS..."
aws ec2 authorize-security-group-ingress \
  --group-id $RDS_SG_ID \
  --protocol tcp \
  --port 3306 \
  --source-group $ECS_SG_ID \
  --region $AWS_REGION

echo "==> Registering task definition..."
cat > /tmp/task-def.json << EOF
{
  "family": "autojobber",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "taskRoleArn": "$TASK_ROLE_ARN",
  "executionRoleArn": "$EXEC_ROLE_ARN",
  "containerDefinitions": [{
    "name": "autojobber",
    "image": "$IMAGE",
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
  }]
}
EOF
aws ecs register-task-definition --cli-input-json file:///tmp/task-def.json --region $AWS_REGION --no-cli-pager
rm /tmp/task-def.json

echo "==> Running task..."
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
echo "==> Saving vars for EventBridge script..."
echo "ECS_SG_ID=$ECS_SG_ID" >> deploy/.deploy_vars
echo "SUBNET_ID=$SUBNET_ID" >> deploy/.deploy_vars
echo "CLUSTER_NAME=$CLUSTER_NAME" >> deploy/.deploy_vars

echo ""
echo "==> Task is running. Tailing CloudWatch logs (Ctrl+C to stop)..."
echo "    To re-tail later: aws logs tail /ecs/autojobber --follow --region $AWS_REGION"
echo ""
sleep 10
aws logs tail /ecs/autojobber --follow --region $AWS_REGION
