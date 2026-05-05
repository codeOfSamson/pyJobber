#!/bin/bash
set -e

ACCOUNT_ID="381076011493"
AWS_REGION="us-east-1"
BUCKET_NAME="autojobber-config-$ACCOUNT_ID"

echo "==> Creating S3 bucket: $BUCKET_NAME"
aws s3api create-bucket \
  --bucket $BUCKET_NAME \
  --region $AWS_REGION

echo "==> Blocking all public access..."
aws s3api put-public-access-block \
  --bucket $BUCKET_NAME \
  --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

echo "==> Uploading config.json..."
aws s3 cp config.json s3://$BUCKET_NAME/config.json

echo "==> Uploading resume.pdf..."
aws s3 cp resume.pdf s3://$BUCKET_NAME/resume.pdf

echo "==> Verifying..."
aws s3 ls s3://$BUCKET_NAME/

echo "==> Done. Bucket: $BUCKET_NAME"
