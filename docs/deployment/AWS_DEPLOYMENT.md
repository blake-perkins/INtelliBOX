# AWS Deployment Guide for INtelliBOX

This guide covers deploying INtelliBOX as a containerized application on AWS.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         AWS Cloud                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐      ┌──────────────┐    ┌────────────┐  │
│  │ ECS Fargate  │─────▶│   RDS        │    │  S3 Bucket │  │
│  │ (Scheduler)  │      │ PostgreSQL   │    │  (.eml)    │  │
│  └──────────────┘      └──────────────┘    └────────────┘  │
│         │                                          │         │
│         │                                          │         │
│  ┌──────▼──────┐      ┌──────────────┐                    │
│  │   EFS       │      │   Secrets    │                    │
│  │  Storage    │      │   Manager    │                    │
│  └─────────────┘      └──────────────┘                    │
│                                                              │
│  ┌──────────────┐      ┌──────────────┐                    │
│  │   SES        │      │  CloudWatch  │                    │
│  │ (Outbound)   │      │    Logs      │                    │
│  └──────────────┘      └──────────────┘                    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Prerequisites

1. **AWS CLI** installed and configured
2. **Docker** or **Podman** installed locally
3. **AWS Account** with appropriate permissions
4. **Domain** (optional, for SES email sending)

## Deployment Options

### Option 1: ECS Fargate (Recommended)
- Serverless container orchestration
- Auto-scaling and high availability
- Best for production workloads

### Option 2: Lambda + EventBridge
- Serverless function execution
- Cost-effective for low-volume usage
- Good for simple scheduled tasks

### Option 3: EC2 with Docker
- Full control over infrastructure
- Good for hybrid environments
- Requires more maintenance

---

## Option 1: ECS Fargate Deployment

### 1. Setup AWS Infrastructure

#### Create VPC and Networking
```bash
# Create VPC
aws ec2 create-vpc --cidr-block 10.0.0.0/16 --region us-east-1

# Create subnets
aws ec2 create-subnet --vpc-id vpc-xxx --cidr-block 10.0.1.0/24 --availability-zone us-east-1a
aws ec2 create-subnet --vpc-id vpc-xxx --cidr-block 10.0.2.0/24 --availability-zone us-east-1b
```

#### Create RDS PostgreSQL Database
```bash
aws rds create-db-instance \
    --db-instance-identifier intellibox-db \
    --db-instance-class db.t4g.micro \
    --engine postgres \
    --engine-version 16.1 \
    --master-username intellibox \
    --master-user-password YOUR_PASSWORD \
    --allocated-storage 20 \
    --vpc-security-group-ids sg-xxx \
    --db-subnet-group-name intellibox-subnet-group \
    --backup-retention-period 7 \
    --publicly-accessible false
```

#### Create EFS for Email Storage
```bash
aws efs create-file-system \
    --region us-east-1 \
    --performance-mode generalPurpose \
    --throughput-mode bursting \
    --encrypted \
    --tags Key=Name,Value=intellibox-efs

# Create access point
aws efs create-access-point \
    --file-system-id fs-xxx \
    --posix-user Uid=1000,Gid=1000 \
    --root-directory Path=/intellibox,CreationInfo={OwnerUid=1000,OwnerGid=1000,Permissions=755}
```

#### Store Secrets in Secrets Manager
```bash
# OpenAI API Key
aws secretsmanager create-secret \
    --name intellibox/openai-api-key \
    --secret-string "sk-proj-your-api-key"

# SMTP Password
aws secretsmanager create-secret \
    --name intellibox/smtp-password \
    --secret-string "your-smtp-password"
```

### 2. Create IAM Roles

#### ECS Task Execution Role
```bash
aws iam create-role \
    --role-name ecsTaskExecutionRole \
    --assume-role-policy-document file://aws/ecs-task-execution-trust-policy.json

aws iam attach-role-policy \
    --role-name ecsTaskExecutionRole \
    --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
```

#### INtelliBOX Task Role (for accessing AWS services)
```bash
aws iam create-role \
    --role-name intelliboxTaskRole \
    --assume-role-policy-document file://aws/ecs-task-trust-policy.json

# Attach policies for S3, SES, Secrets Manager
aws iam attach-role-policy \
    --role-name intelliboxTaskRole \
    --policy-arn arn:aws:iam::aws:policy/AmazonSESFullAccess
```

### 3. Update Configuration

Edit `aws/ecs-task-definition.json`:
- Replace `YOUR_ACCOUNT_ID` with your AWS account ID
- Update database connection string
- Update EFS file system ID
- Update secret ARNs

### 4. Deploy Application

```bash
# Make deploy script executable
chmod +x aws/deploy.sh

# Set environment variables
export AWS_REGION=us-east-1
export IMAGE_TAG=v1.0.0

# Run deployment
./aws/deploy.sh
```

### 5. Create ECS Cluster and Service

```bash
# Create cluster
aws ecs create-cluster \
    --cluster-name intellibox-cluster \
    --region us-east-1

# Create service
aws ecs create-service \
    --cluster intellibox-cluster \
    --service-name intellibox-scheduler \
    --task-definition intellibox-scheduler:1 \
    --desired-count 1 \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx,subnet-yyy],securityGroups=[sg-xxx],assignPublicIp=DISABLED}" \
    --region us-east-1
```

### 6. Configure Auto-scaling (Optional)

```bash
aws application-autoscaling register-scalable-target \
    --service-namespace ecs \
    --resource-id service/intellibox-cluster/intellibox-scheduler \
    --scalable-dimension ecs:service:DesiredCount \
    --min-capacity 1 \
    --max-capacity 3
```

---

## Option 2: Lambda Deployment

### 1. Package Application for Lambda

```bash
# Build Docker image for Lambda
docker build -f aws/Dockerfile.lambda -t intellibox-lambda .

# Push to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com
docker tag intellibox-lambda:latest YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/intellibox-lambda:latest
docker push YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/intellibox-lambda:latest
```

### 2. Create Lambda Function

```bash
aws lambda create-function \
    --function-name intellibox-report-generator \
    --package-type Image \
    --code ImageUri=YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/intellibox-lambda:latest \
    --role arn:aws:iam::YOUR_ACCOUNT:role/lambda-execution-role \
    --timeout 900 \
    --memory-size 512 \
    --environment Variables="{DATABASE_URL=postgresql://...,OPENAI_API_KEY=sk-...}"
```

### 3. Create EventBridge Schedule

```bash
aws events put-rule \
    --name intellibox-daily-report \
    --schedule-expression "cron(0 6 * * ? *)" \
    --state ENABLED

aws events put-targets \
    --rule intellibox-daily-report \
    --targets "Id"="1","Arn"="arn:aws:lambda:us-east-1:YOUR_ACCOUNT:function:intellibox-report-generator"
```

---

## Database Migration

Run migrations after initial deployment:

```bash
# Via ECS Exec (recommended)
aws ecs execute-command \
    --cluster intellibox-cluster \
    --task TASK_ID \
    --container intellibox \
    --interactive \
    --command "alembic upgrade head"

# Or via one-time task
aws ecs run-task \
    --cluster intellibox-cluster \
    --task-definition intellibox-scheduler \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[subnet-xxx],securityGroups=[sg-xxx]}" \
    --overrides '{"containerOverrides":[{"name":"intellibox","command":["alembic","upgrade","head"]}]}'
```

---

## Email Ingestion Options

### Option A: Web Upload (Recommended)
Upload `.eml` or `.msg` files directly through the INtelliBOX dashboard at `/emails/upload`. This is the primary ingestion method.

### Option B: File Drop (File Watcher)
Drop `.eml` or `.msg` files into the `data/inbox/` directory. The built-in file watcher picks them up automatically. Works with SCP, OneDrive/SharePoint sync, or any folder-based integration.

### Option C: S3 + Lambda Trigger
1. Create S3 bucket for email uploads
2. Configure Lambda to trigger on new .eml/.msg files
3. Process emails and store in database

### Option D: SES Receipt Rule
1. Configure SES to receive emails
2. Store raw emails in S3
3. Trigger Lambda/ECS task to process

---

## Monitoring and Logging

### CloudWatch Logs
```bash
# View real-time logs
aws logs tail /ecs/intellibox --follow

# Create log insights query
aws logs insights \
    --log-group-name /ecs/intellibox \
    --query-string 'fields @timestamp, @message | filter @message like /ERROR/ | sort @timestamp desc'
```

### CloudWatch Alarms
```bash
# Alert on errors
aws cloudwatch put-metric-alarm \
    --alarm-name intellibox-high-error-rate \
    --comparison-operator GreaterThanThreshold \
    --evaluation-periods 1 \
    --metric-name Errors \
    --namespace AWS/ECS \
    --period 300 \
    --statistic Sum \
    --threshold 10
```

---

## Cost Estimation

### ECS Fargate (24/7 operation)
- **Compute**: ~$15/month (0.25 vCPU, 0.5 GB RAM)
- **RDS**: ~$15/month (db.t4g.micro)
- **EFS**: ~$5/month (5 GB storage)
- **Data Transfer**: ~$5/month
- **Total**: **~$40/month**

### Lambda (scheduled reports only)
- **Lambda**: ~$2/month (daily execution)
- **RDS**: ~$15/month (same as above)
- **S3**: ~$1/month (email storage)
- **Total**: **~$18/month**

### OpenAI API
- **50-100 emails/day**: ~$10/month
- **Add to above costs**

---

## Security Best Practices

1. **Never commit secrets** - use AWS Secrets Manager
2. **Use VPC** - keep RDS and EFS private
3. **Enable encryption** - for RDS, EFS, and S3
4. **IAM least privilege** - only grant necessary permissions
5. **Enable AWS WAF** - if exposing HTTP endpoints
6. **Rotate credentials** - regularly update secrets
7. **Enable CloudTrail** - audit all API calls

---

## Troubleshooting

### Container won't start
```bash
# Check task logs
aws ecs describe-tasks --cluster intellibox-cluster --tasks TASK_ID

# View stopped tasks
aws ecs list-tasks --cluster intellibox-cluster --desired-status STOPPED
```

### Database connection issues
```bash
# Test connectivity from container
aws ecs execute-command \
    --cluster intellibox-cluster \
    --task TASK_ID \
    --container intellibox \
    --interactive \
    --command "psql $DATABASE_URL -c 'SELECT 1'"
```

### High costs
```bash
# Check CloudWatch metrics
aws cloudwatch get-metric-statistics \
    --namespace AWS/ECS \
    --metric-name CPUUtilization \
    --dimensions Name=ClusterName,Value=intellibox-cluster \
    --statistics Average \
    --start-time 2026-01-01T00:00:00Z \
    --end-time 2026-01-31T23:59:59Z \
    --period 3600
```

---

## Current Deployment

The project currently deploys to an EC2 instance using Podman with an IronBank UBI 9 container image. CI/CD is handled by GitHub Actions — pushes to `main` auto-deploy after all tests and security scans pass. See [deploy/README.md](../../deploy/README.md) for the production deployment guide.

The ECS Fargate and Lambda options above are alternative architectures for teams that prefer managed AWS services.

## Next Steps

1. Configure custom domain for SES
2. Implement backup and disaster recovery
3. Set up monitoring dashboards
4. Configure auto-scaling policies

For questions or issues, refer to the main README.md or create an issue on GitHub.
