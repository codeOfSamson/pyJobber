#!/bin/bash
set -e

ACCOUNT_ID="381076011493"
AWS_REGION="us-east-1"
ECR_URL="$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
IMAGE="$ECR_URL/autojobber:latest"

echo "==> Logging in to ECR..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_URL

echo "==> Building image for linux/amd64..."
docker build --platform linux/amd64 -t autojobber:latest .

echo "==> Tagging image..."
docker tag autojobber:latest $IMAGE

echo "==> Pushing image..."
docker push $IMAGE

echo "==> Done: $IMAGE"
