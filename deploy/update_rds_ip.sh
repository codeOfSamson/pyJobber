#!/bin/bash
set -e

AWS_REGION="us-east-1"
RDS_SG_ID="sg-0bc0ed4f6f594cd85"

export AWS_PROFILE=personal

MY_IP=$(curl -s https://checkip.amazonaws.com)
echo "==> Your current IP: $MY_IP"

OLD_CIDR=$(aws ec2 describe-security-groups \
  --group-ids $RDS_SG_ID \
  --query "SecurityGroups[0].IpPermissions[?FromPort==\`3306\`].IpRanges[0].CidrIp" \
  --output text \
  --region $AWS_REGION)

if [ -n "$OLD_CIDR" ] && [ "$OLD_CIDR" != "None" ]; then
  echo "==> Removing old IP: $OLD_CIDR"
  aws ec2 revoke-security-group-ingress \
    --group-id $RDS_SG_ID \
    --protocol tcp --port 3306 \
    --cidr $OLD_CIDR \
    --region $AWS_REGION
fi

echo "==> Adding new IP: $MY_IP/32"
aws ec2 authorize-security-group-ingress \
  --group-id $RDS_SG_ID \
  --protocol tcp --port 3306 \
  --cidr $MY_IP/32 \
  --region $AWS_REGION

echo "==> Done. TablePlus should connect now."
