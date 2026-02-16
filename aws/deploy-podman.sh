#!/bin/bash
# EmailTools AWS Deployment Script (Podman-compatible)
# Works with both Docker and Podman

set -e

# Detect container engine (prefer Podman, fallback to Docker)
if command -v podman &> /dev/null; then
    CONTAINER_ENGINE="${CONTAINER_ENGINE:-podman}"
elif command -v docker &> /dev/null; then
    CONTAINER_ENGINE="${CONTAINER_ENGINE:-docker}"
else
    echo "Error: Neither Podman nor Docker found. Please install one."
    exit 1
fi

echo "Using container engine: $CONTAINER_ENGINE"

# Configuration
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-$(aws sts get-caller-identity --query Account --output text)}"
ECR_REPO_NAME="emailtools"
IMAGE_TAG="${IMAGE_TAG:-latest}"
ECS_CLUSTER="emailtools-cluster"
ECS_SERVICE="emailtools-scheduler"
PLATFORM="${PLATFORM:-linux/amd64}"  # or linux/arm64 for Graviton

echo "======================================"
echo "EmailTools AWS Deployment (Podman)"
echo "======================================"
echo "Container Engine: $CONTAINER_ENGINE"
echo "Region: $AWS_REGION"
echo "Account: $AWS_ACCOUNT_ID"
echo "Image: $ECR_REPO_NAME:$IMAGE_TAG"
echo "Platform: $PLATFORM"
echo ""

# Step 1: Create ECR repository if it doesn't exist
echo "[1/6] Creating ECR repository..."
aws ecr describe-repositories --repository-names $ECR_REPO_NAME --region $AWS_REGION > /dev/null 2>&1 || \
    aws ecr create-repository \
        --repository-name $ECR_REPO_NAME \
        --region $AWS_REGION \
        --image-scanning-configuration scanOnPush=true \
        --encryption-configuration encryptionType=AES256

# Step 2: Build image
echo "[2/6] Building container image..."
$CONTAINER_ENGINE build \
    --platform $PLATFORM \
    -t $ECR_REPO_NAME:$IMAGE_TAG \
    -f Dockerfile \
    .

# Step 3: Login to ECR
echo "[3/6] Logging in to ECR..."
aws ecr get-login-password --region $AWS_REGION | \
    $CONTAINER_ENGINE login --username AWS --password-stdin \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Step 4: Tag and push image
echo "[4/6] Tagging and pushing image..."
$CONTAINER_ENGINE tag \
    $ECR_REPO_NAME:$IMAGE_TAG \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME:$IMAGE_TAG

$CONTAINER_ENGINE push \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME:$IMAGE_TAG

# Step 5: Update task definition with new image
echo "[5/6] Updating ECS task definition..."

# Create temporary file with updated image
TEMP_TASK_DEF=$(mktemp)
jq --arg IMAGE "$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPO_NAME:$IMAGE_TAG" \
   '.containerDefinitions[0].image = $IMAGE' \
   aws/ecs-task-definition.json > $TEMP_TASK_DEF

# Register new task definition
TASK_DEF_ARN=$(aws ecs register-task-definition \
    --cli-input-json file://$TEMP_TASK_DEF \
    --region $AWS_REGION \
    --query 'taskDefinition.taskDefinitionArn' \
    --output text)

rm $TEMP_TASK_DEF

echo "Task definition: $TASK_DEF_ARN"

# Step 6: Update ECS service
echo "[6/6] Updating ECS service..."
aws ecs update-service \
    --cluster $ECS_CLUSTER \
    --service $ECS_SERVICE \
    --task-definition $TASK_DEF_ARN \
    --force-new-deployment \
    --region $AWS_REGION \
    --no-cli-pager

echo ""
echo "======================================"
echo "Deployment complete!"
echo "======================================"
echo ""
echo "Monitor deployment:"
echo "  aws ecs describe-services --cluster $ECS_CLUSTER --services $ECS_SERVICE --region $AWS_REGION"
echo ""
echo "View logs:"
echo "  aws logs tail /ecs/emailtools --follow --region $AWS_REGION"
echo ""
echo "Run one-time task:"
echo "  aws ecs run-task --cluster $ECS_CLUSTER --task-definition $TASK_DEF_ARN --launch-type FARGATE"
