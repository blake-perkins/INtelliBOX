#!/bin/bash
# INtelliBOX AWS Deployment Script
# Deploys containerized application to AWS ECS Fargate

set -e

# Configuration
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
ECR_REPO_NAME="intellibox"
IMAGE_TAG="${IMAGE_TAG:-latest}"
ECS_CLUSTER="intellibox-cluster"
ECS_SERVICE="intellibox-scheduler"

echo "======================================"
echo "INtelliBOX AWS Deployment"
echo "======================================"
echo "Region: $AWS_REGION"
echo "Account: $AWS_ACCOUNT_ID"
echo "Image: $ECR_REPO_NAME:$IMAGE_TAG"
echo ""

# Step 1: Create ECR repository if it doesn't exist
echo "[1/6] Creating ECR repository..."
aws ecr describe-repositories --repository-names $ECR_REPO_NAME --region $AWS_REGION > /dev/null 2>&1 || \
    aws ecr create-repository \
        --repository-name $ECR_REPO_NAME \
        --region $AWS_REGION \
        --image-scanning-configuration scanOnPush=true

# Step 2: Build Docker image
echo "[2/6] Building Docker image..."
docker build -t $ECR_REPO_NAME:$IMAGE_TAG .

# Step 3: Login to ECR
echo "[3/6] Logging in to ECR..."
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Step 4: Tag and push image
echo "[4/6] Tagging and pushing image..."
docker tag $ECR_REPO_NAME:$IMAGE_TAG $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME:$IMAGE_TAG
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME:$IMAGE_TAG

# Step 5: Register task definition
echo "[5/6] Registering ECS task definition..."
TASK_DEF_ARN=$(aws ecs register-task-definition \
    --cli-input-json file://aws/ecs-task-definition.json \
    --region $AWS_REGION \
    --query 'taskDefinition.taskDefinitionArn' \
    --output text)

echo "Task definition: $TASK_DEF_ARN"

# Step 6: Update ECS service
echo "[6/6] Updating ECS service..."
aws ecs update-service \
    --cluster $ECS_CLUSTER \
    --service $ECS_SERVICE \
    --task-definition $TASK_DEF_ARN \
    --force-new-deployment \
    --region $AWS_REGION

echo ""
echo "======================================"
echo "Deployment complete!"
echo "======================================"
echo "Monitor deployment:"
echo "  aws ecs describe-services --cluster $ECS_CLUSTER --services $ECS_SERVICE --region $AWS_REGION"
echo ""
echo "View logs:"
echo "  aws logs tail /ecs/intellibox --follow --region $AWS_REGION"
