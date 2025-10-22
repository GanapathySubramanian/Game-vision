# Gameplay Analysis - Backend

FastAPI-based backend service for video gameplay analysis using AWS Bedrock Agent and Data Automation.

## 🎯 Overview

A Python backend that provides:
- **Video Upload API**: Direct S3 upload with presigned URLs
- **Bedrock Agent Integration**: AI-powered gameplay analysis and Q&A
- **Lambda Functions**: Serverless video processing and analysis
- **Real-time Chat**: WebSocket support for interactive conversations
- **Data Automation**: Automated video analysis using Bedrock blueprints

## 🛠️ Tech Stack

- **Python 3.11+** with FastAPI
- **AWS Bedrock** (Nova pro)
- **AWS Lambda** for serverless processing
- **AWS S3** for video storage
- **Bedrock Data Automation** for video analysis
- **Boto3** for AWS SDK

## 📋 Prerequisites

- **Python 3.11+** and pip
- **AWS CLI** configured with credentials
- **AWS Account** with access to:
  - S3
  - Lambda
  - Bedrock (Agent and Data Automation)
  - IAM
  - Elastic Beanstalk (for deployment)

## 🚀 Local Development Setup

### 1. Install Dependencies

```bash
cd bedrock-agent/backend
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create `.env` file:

```bash
# AWS Configuration
AWS_REGION=us-east-1
AWS_BUCKET_NAME=your-video-bucket-name

# Bedrock Agent
BEDROCK_AGENT_ID=your-agent-id
BEDROCK_AGENT_ALIAS_ID=your-alias-id

# Lambda Functions (ARNs)
VIDEO_PROCESSOR_ARN=arn:aws:lambda:us-east-1:123456789012:function:gameplay-video-processor
ANALYSIS_PROCESSOR_ARN=arn:aws:lambda:us-east-1:123456789012:function:gameplay-analysis-processor
QUERY_HANDLER_ARN=arn:aws:lambda:us-east-1:123456789012:function:gameplay-query-handler

# Optional
LOG_LEVEL=INFO
```

**Note:** Use `.env.example` as a template.

### 3. Set Up AWS Infrastructure

#### Option A: Automated Setup (Recommended)

Use the deployment script from the infrastructure directory:

```bash
cd bedrock-agent/infrastructure
./deploy.sh infra-setup
```

This will automatically:
- ✅ Create IAM role: `GameplayAnalysisLambdaRole`
- ✅ Create S3 bucket with proper policies
- ✅ Deploy 3 Lambda functions
- ✅ Generate `backend/.env` with all ARNs

#### Option B: Manual Setup

**1. Create IAM Role for Lambda:**

```bash
# Create trust policy
cat > /tmp/lambda-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create role
aws iam create-role \
  --role-name GameplayAnalysisLambdaRole \
  --assume-role-policy-document file:///tmp/lambda-trust-policy.json

# Attach policies
aws iam attach-role-policy \
  --role-name GameplayAnalysisLambdaRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess

aws iam attach-role-policy \
  --role-name GameplayAnalysisLambdaRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess

aws iam attach-role-policy \
  --role-name GameplayAnalysisLambdaRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
```

**2. Create S3 Bucket:**

```bash
# Create bucket
aws s3 mb s3://gameplay-analysis-videos-$(date +%s) --region us-east-1

# Enable CORS
aws s3api put-bucket-cors \
  --bucket your-bucket-name \
  --cors-configuration file://s3-cors-config.json
```

**3. Deploy Lambda Functions:**

```bash
cd lambda-functions

# Package and deploy each function
for func in video_processor analysis_processor query_handler; do
  zip ${func}.zip ${func}.py ../shared/aws_helpers.py
  
  aws lambda create-function \
    --function-name gameplay-${func//_/-} \
    --runtime python3.11 \
    --role arn:aws:iam::ACCOUNT_ID:role/GameplayAnalysisLambdaRole \
    --handler ${func}.lambda_handler \
    --zip-file fileb://${func}.zip \
    --timeout 300 \
    --memory-size 512
done
```

**4. Create Bedrock Agent:**

See `bedrock-agent/agent_config.json` for configuration. Create via AWS Console:
1. Go to **Bedrock** → **Agents** → **Create Agent**
2. Use Claude 3.5 Sonnet model or Nova model or anything you like to use
3. Add 3 action groups (one for each Lambda function)
4. Use schemas from `bedrock-agent/` directory
5. Note the Agent ID and Alias ID

### 4. Start Development Server

```bash
# Start FastAPI server
python api_server.py
```

Server runs at `http://localhost:8000`

## 📁 Project Structure

```
backend/
├── api_server.py                    # Main FastAPI application
├── requirements.txt                 # Python dependencies
├── .env                            # Environment variables (not in Git)
├── .env.example                    # Environment template
├── Procfile                        # Elastic Beanstalk config
├── .ebignore                       # EB deployment exclusions
├── lambda-functions/               # AWS Lambda functions
│   ├── video_processor.py          # Handles video uploads
│   ├── analysis_processor.py       # Processes videos with BDA
│   └── query_handler.py            # Handles Q&A queries
├── bedrock-agent/                  # Bedrock Agent configuration
│   ├── agent_config.json           # Agent setup
│   ├── video-management-schema.json
│   ├── gameplay-analysis-schema.json
│   └── query-interface-schema.json
├── bedrock-data-automation/        # BDA blueprints
│   └── game-analysis-blueprint.json
├── shared/                         # Shared utilities
│   └── aws_helpers.py              # AWS SDK helpers
└── README.md                       # This file
```

## 🔌 API Endpoints

### Health Check
```bash
GET /health
```

Returns server status and configuration.

### Upload Video
```bash
POST /upload
Content-Type: application/json

{
  "filename": "gameplay.mp4",
  "content_type": "video/mp4"
}
```

Returns presigned S3 URL for direct upload.

### Chat with Agent
```bash
POST /chat
Content-Type: application/json

{
  "message": "What happened in the first 30 seconds?",
  "session_id": "unique-session-id",
  "video_id": "optional-video-id"
}
```

Returns AI-generated response about the video.

### Get Analysis Status
```bash
GET /analysis/{video_id}
```

Returns current analysis status and results.

## 🚀 Deployment Options

You can deploy the backend using either:
1. **Elastic Beanstalk** (Recommended) - Easiest, most reliable
2. **ECS Fargate** (Advanced) - Containerized, requires careful network setup
3. **AWS App Runner** (Alternative) - Simplest container deployment

---

## 🏢 AWS Elastic Beanstalk Deployment (Recommended)

### Why Elastic Beanstalk?
- ✅ Easiest to set up and manage
- ✅ Built-in load balancing and auto-scaling
- ✅ Integrated monitoring and logging
- ✅ No complex networking configuration
- ✅ Proven reliability

### Prerequisites

```bash
# Install EB CLI
pip install awsebcli --upgrade --user

# Verify installation
eb --version
```

### Quick Deployment (3 Steps)

#### Step 1: Initialize EB Application

```bash
cd bedrock-agent/backend

# Initialize EB
eb init -p python-3.11 gameplay-analysis-backend --region us-east-1
```

#### Step 2: Create IAM Instance Profile

Your EB instances need AWS permissions. Create an IAM role:

```bash
# Use the deployment script (recommended)
cd ../infrastructure
./deploy-to-eb.sh create-role

# Or create manually (see manual setup section below)
```

#### Step 3: Create & Deploy Environment

```bash
# Create environment
eb create gameplay-analysis-env \
  --instance-type t3.small \
  --instance-profile gameplay-analysis-eb-role \
  --region us-east-1

# This takes 5-10 minutes ☕
```

### Deployment Script (Easiest Method)

Use the provided deployment script:

```bash
cd bedrock-agent/infrastructure

# Complete deployment
./deploy-to-eb.sh deploy

# Or step by step:
./deploy-to-eb.sh init          # Initialize EB
./deploy-to-eb.sh create-role   # Create IAM role
./deploy-to-eb.sh create        # Create environment
./deploy-to-eb.sh url           # Get backend URL
```

### Update Environment Variables

After deployment, set environment variables:

```bash
# Set all variables at once
eb setenv \
  AWS_REGION=us-east-1 \
  AWS_BUCKET_NAME=your-bucket \
  BEDROCK_AGENT_ID=your-agent-id \
  BEDROCK_AGENT_ALIAS_ID=your-alias-id \
  VIDEO_PROCESSOR_ARN=your-lambda-arn \
  ANALYSIS_PROCESSOR_ARN=your-lambda-arn \
  QUERY_HANDLER_ARN=your-lambda-arn
```

### Deploy Updates

```bash
# Deploy code changes
eb deploy

# View logs
eb logs

# Check status
eb status
```

### Get Backend URL

```bash
# Via EB CLI
eb status | grep CNAME

# Or use script
cd ../infrastructure
./deploy-to-eb.sh url
```

You'll get: `http://gameplay-analysis-env.us-east-1.elasticbeanstalk.com`

---

## 🐳 AWS ECS Fargate Deployment (Advanced)

### ⚠️ Important Considerations

ECS Fargate deployment requires careful network configuration and can encounter AWS rate limits. **Only use this if you need containerization or have specific requirements.**

### Common Issues & Solutions

**Issue: Network Interface Rate Limits**
- AWS limits network interface creation (~50-100/hour per subnet)
- Repeated deployment failures can trigger rate limits
- **Solution**: Wait 3-4 hours between deployment attempts

**Issue: VPC Endpoint Complexity**
- Private subnets require VPC endpoints for ECR access
- VPC endpoints cost ~$7/month per endpoint
- Configuration can be complex
- **Solution**: Use NAT Gateway or public subnets with internet gateway

**Issue: Health Check Failures**
- Default health checks may be too aggressive
- Application needs 90-120 seconds to start
- **Solution**: Configure health check with 120s grace period

### Prerequisites
- Docker installed and running
- AWS CLI configured
- Understanding of VPC networking
- `backend/.env` file configured

### Network Configuration Options

#### Option 1: Public Subnets + Internet Gateway (Simplest)
- ✅ Free
- ✅ No VPC endpoints needed
- ⚠️ Can hit rate limits with repeated deployments
- **Best for**: Development, testing

#### Option 2: Private Subnets + NAT Gateway (Production)
- ✅ No rate limit issues
- ✅ More secure
- ❌ Costs ~$32/month
- **Best for**: Production deployments

#### Option 3: Private Subnets + VPC Endpoints
- ✅ No NAT Gateway costs
- ❌ Complex setup
- ❌ VPC endpoints cost ~$21/month (3 endpoints)
- **Best for**: High-security requirements

### Deployment Steps

#### 1. Test Docker Image Locally First

```bash
cd bedrock-agent/backend

# Build image
docker build -t gameplay-analysis-backend:test .

# Test locally with AWS credentials
docker run -p 8000:8000 \
  --env-file .env \
  -e AWS_ACCESS_KEY_ID=$(aws configure get aws_access_key_id) \
  -e AWS_SECRET_ACCESS_KEY=$(aws configure get aws_secret_access_key) \
  gameplay-analysis-backend:test

# Test health endpoint
curl http://localhost:8000/health
```

#### 2. Deploy to ECS

```bash
cd ../infrastructure

# Complete deployment
./deploy-to-ecs.sh deploy
```

**Time:** 15-20 minutes | **Result:** Backend with public ALB URL

### Deployment Commands

```bash
# Complete deployment
./deploy-to-ecs.sh deploy

# Deploy with existing image (skip build)
./deploy-to-ecs.sh deploy-only

# Update after code changes
./deploy-to-ecs.sh update

# Get backend URL
./deploy-to-ecs.sh url

# Check status
./deploy-to-ecs.sh status

# View logs
./deploy-to-ecs.sh logs

# Cleanup
./deploy-to-ecs.sh cleanup
```

### What Gets Created
- ECR repository for Docker images
- ECS Fargate cluster
- Application Load Balancer (ALB)
- ECS service with auto-scaling
- Security groups and IAM roles
- (Optional) NAT Gateway or VPC endpoints

### Cost Estimate

**With Public Subnets:**
- Fargate: ~$15-20/month (0.25 vCPU, 0.5GB RAM)
- ALB: ~$16/month
- **Total**: ~$30-35/month

**With NAT Gateway:**
- Fargate: ~$15-20/month
- ALB: ~$16/month
- NAT Gateway: ~$32/month
- **Total**: ~$63-68/month

### Troubleshooting ECS Deployment

**Rate Limit Errors:**
```
Rate limit exceeded while attempting to Create Network Interface
```
**Solution:**
1. Stop the ECS service: `./deploy-to-ecs.sh` → set desired-count to 0
2. Wait 3-4 hours for rate limits to reset
3. Try deployment again

**Network Timeout Errors:**
```
unable to pull secrets or registry auth: connection timeout
```
**Solution:**
1. Verify subnets have internet access (internet gateway or NAT gateway)
2. Check security groups allow outbound HTTPS (port 443)
3. Consider using VPC endpoints for ECR

**Health Check Failures:**
```
Task failed ELB health checks
```
**Solution:**
1. Increase health check grace period to 120 seconds
2. Verify application starts within 90 seconds
3. Check CloudWatch logs for application errors

### Update Workflow
1. Make code changes
2. Test Docker image locally
3. Run `./deploy-to-ecs.sh update`
4. Monitor deployment (3-5 minutes)
5. Verify with health check

---

## 🚀 AWS App Runner Deployment (Alternative)

### Why App Runner?
- ✅ Simplest container deployment
- ✅ No VPC configuration needed
- ✅ Auto-scaling built-in
- ✅ No rate limit issues
- ❌ Less control than ECS

### Quick Deployment

```bash
# Build and push to ECR
cd bedrock-agent/infrastructure
./build-and-push.sh

# Create App Runner service via AWS Console
# 1. Go to App Runner console
# 2. Create service from ECR
# 3. Select your image
# 4. Configure environment variables
# 5. Deploy
```

**Cost:** ~$25-40/month (similar to ECS)

---

## 🏢 AWS Elastic Beanstalk Deployment

### Prerequisites

```bash
# Install EB CLI
pip install awsebcli --upgrade --user

# Verify installation
eb --version
```

### Quick Deployment (3 Steps)

#### Step 1: Initialize EB Application

```bash
cd bedrock-agent/backend

# Initialize EB
eb init -p python-3.11 gameplay-analysis-backend --region us-east-1
```

#### Step 2: Create IAM Instance Profile

Your EB instances need AWS permissions. Create an IAM role:

```bash
# Create trust policy
cat > /tmp/eb-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create role
aws iam create-role \
  --role-name gameplay-analysis-eb-role \
  --assume-role-policy-document file:///tmp/eb-trust-policy.json

# Attach required policies
aws iam attach-role-policy \
  --role-name gameplay-analysis-eb-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess

aws iam attach-role-policy \
  --role-name gameplay-analysis-eb-role \
  --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess

aws iam attach-role-policy \
  --role-name gameplay-analysis-eb-role \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaRole

aws iam attach-role-policy \
  --role-name gameplay-analysis-eb-role \
  --policy-arn arn:aws:iam::aws:policy/CloudWatchLogsFullAccess

# Create instance profile
aws iam create-instance-profile \
  --instance-profile-name gameplay-analysis-eb-role

# Add role to instance profile
aws iam add-role-to-instance-profile \
  --instance-profile-name gameplay-analysis-eb-role \
  --role-name gameplay-analysis-eb-role
```

#### Step 3: Create & Deploy Environment

```bash
# Create environment
eb create gameplay-analysis-env \
  --instance-type t3.small \
  --instance-profile gameplay-analysis-eb-role \
  --region us-east-1

# This takes 5-10 minutes ☕
```

### Deployment Script (Alternative)

Use the provided deployment script from the infrastructure directory:

```bash
cd ../infrastructure

# Initialize
./deploy-to-eb.sh init

# Create IAM role
./deploy-to-eb.sh create-role

# Create environment
./deploy-to-eb.sh create

# Get URL
./deploy-to-eb.sh url
```

### Update Environment Variables

After deployment, set environment variables in EB:

```bash
# Set all variables at once
eb setenv \
  AWS_REGION=us-east-1 \
  AWS_BUCKET_NAME=your-bucket \
  BEDROCK_AGENT_ID=your-agent-id \
  BEDROCK_AGENT_ALIAS_ID=your-alias-id \
  VIDEO_PROCESSOR_ARN=your-lambda-arn \
  ANALYSIS_PROCESSOR_ARN=your-lambda-arn \
  QUERY_HANDLER_ARN=your-lambda-arn
```

Or configure via AWS Console:
1. Go to **Elastic Beanstalk** → Your Environment
2. **Configuration** → **Software** → **Environment properties**
3. Add all variables from `.env`

### Deploy Updates

```bash
# Deploy code changes
eb deploy

# View logs
eb logs

# Check status
eb status

# Open in browser
eb open
```

### Get Backend URL

```bash
# Via EB CLI
eb status | grep CNAME

# Or use script
./deploy-to-eb.sh url
```

You'll get: `http://gameplay-analysis-env.us-east-1.elasticbeanstalk.com`

**Update frontend** with this URL (see frontend README).

## 🧪 Testing

### Test Health Endpoint

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-20T12:00:00",
  "version": "2.0.0",
  "aws_region": "us-east-1",
  "bedrock_agent_configured": true
}
```

### Test Upload Endpoint

```bash
curl -X POST http://localhost:8000/upload \
  -H "Content-Type: application/json" \
  -d '{"filename": "test.mp4", "content_type": "video/mp4"}'
```

### Test Chat Endpoint

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Analyze this video",
    "session_id": "test-session"
  }'
```

### Test Lambda Functions

```bash
# Invoke video processor
aws lambda invoke \
  --function-name gameplay-video-processor \
  --payload '{"video_key": "test.mp4"}' \
  response.json

# Check response
cat response.json
```

## 🐛 Troubleshooting

### Issue: "Module not found" errors

**Fix:**
```bash
# Reinstall dependencies
pip install -r requirements.txt

# For EB deployment, ensure requirements.txt is complete
pip freeze > requirements.txt
```

### Issue: AWS credentials not working

**Fix:**
```bash
# Check AWS configuration
aws sts get-caller-identity

# Reconfigure if needed
aws configure
```

### Issue: Lambda function timeout

**Cause:** Video processing takes too long

**Fix:**
```bash
# Increase Lambda timeout (max 15 minutes)
aws lambda update-function-configuration \
  --function-name gameplay-analysis-processor \
  --timeout 900
```

### Issue: Bedrock Agent not responding

**Fix:**
1. Verify Agent ID and Alias ID in `.env`
2. Check Agent is in "Prepared" state in AWS Console
3. Verify Lambda functions are connected as action groups
4. Check CloudWatch logs for errors

### Issue: S3 upload fails with CORS error

**Fix:**
```bash
# Update CORS configuration
aws s3api put-bucket-cors \
  --bucket your-bucket-name \
  --cors-configuration '{
    "CORSRules": [{
      "AllowedOrigins": ["*"],
      "AllowedMethods": ["GET", "PUT", "POST"],
      "AllowedHeaders": ["*"],
      "MaxAgeSeconds": 3000
    }]
  }'
```

### Issue: EB deployment fails

**Common causes:**
- Missing Procfile
- Incorrect Python version
- Missing dependencies
- IAM permissions

**Fix:**
```bash
# Check EB logs
eb logs

# Verify Procfile exists
cat Procfile
# Should contain: web: uvicorn api_server:app --host 0.0.0.0 --port 8000

# Test locally first
python api_server.py
```

### Issue: 502 Bad Gateway on EB

**Cause:** Application not starting or port mismatch

**Fix:**
```bash
# SSH into instance
eb ssh

# Check application logs
sudo tail -f /var/log/eb-engine.log
sudo tail -f /var/log/web.stdout.log

# Verify app is listening on port 8000
sudo netstat -tlnp | grep 8000
```

## 📊 Monitoring and Logs

### Local Logs

```bash
# Application logs
tail -f api_server.log

# Python logs
tail -f *.log
```

### CloudWatch Logs

**Lambda Functions:**
- `/aws/lambda/gameplay-video-processor`
- `/aws/lambda/gameplay-analysis-processor`
- `/aws/lambda/gameplay-query-handler`

**Elastic Beanstalk:**
- `/aws/elasticbeanstalk/gameplay-analysis-env/var/log/web.stdout.log`
- `/aws/elasticbeanstalk/gameplay-analysis-env/var/log/web.stderr.log`

### View Logs via CLI

```bash
# EB logs
eb logs

# Lambda logs
aws logs tail /aws/lambda/gameplay-video-processor --follow

# CloudWatch Insights query
aws logs start-query \
  --log-group-name /aws/lambda/gameplay-video-processor \
  --start-time $(date -u -d '1 hour ago' +%s) \
  --end-time $(date +%s) \
  --query-string 'fields @timestamp, @message | sort @timestamp desc'
```

## 💰 Cost Optimization

### Development Environment
- **EB Instance**: t3.small (~$15/month)
- **Lambda**: Pay per invocation (~$1-5/month)
- **S3**: Storage + requests (~$1-3/month)
- **Bedrock**: Pay per token (~$10-50/month depending on usage)
- **Total**: ~$30-75/month

### Production Environment
- **EB Instance**: t3.medium with auto-scaling (~$50-150/month)
- **Lambda**: Higher invocation volume (~$10-30/month)
- **S3**: More storage (~$5-20/month)
- **Bedrock**: Higher usage (~$50-200/month)
- **Total**: ~$115-400/month

### Cost Reduction Tips
1. **Terminate EB** when not in use: `eb terminate`
2. **Use S3 lifecycle policies** to archive old videos
3. **Set Lambda reserved concurrency** to limit costs
4. **Monitor Bedrock token usage** and optimize prompts
5. **Use spot instances** for non-critical environments

## 🔒 Security Best Practices

### Environment Variables
- Never commit `.env` to Git
- Use AWS Secrets Manager for production
- Rotate credentials regularly

### IAM Permissions
- Follow principle of least privilege
- Use separate roles for different services
- Enable CloudTrail for audit logging

### API Security
- Implement rate limiting
- Add authentication (API keys, JWT)
- Validate all inputs
- Use HTTPS in production

### S3 Security
- Enable bucket encryption
- Use presigned URLs with short expiration
- Block public access
- Enable versioning for important data

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [AWS Bedrock Documentation](https://docs.aws.amazon.com/bedrock/)
- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [Elastic Beanstalk Documentation](https://docs.aws.amazon.com/elasticbeanstalk/)

## 🆘 Common Commands Reference

```bash
# Local Development
python api_server.py                    # Start server
pip install -r requirements.txt         # Install dependencies
python -m pytest                        # Run tests (if available)

# AWS Infrastructure
aws s3 ls s3://your-bucket/            # List S3 contents
aws lambda list-functions              # List Lambda functions
aws iam get-role --role-name RoleName  # Check IAM role

# Elastic Beanstalk
eb init                                # Initialize EB
eb create                              # Create environment
eb deploy                              # Deploy updates
eb status                              # Check status
eb logs                                # View logs
eb ssh                                 # SSH into instance
eb terminate                           # Delete environment

# Deployment Script (from infrastructure directory)
cd ../infrastructure
./deploy-to-eb.sh init                 # Initialize EB
./deploy-to-eb.sh create-role          # Create IAM role
./deploy-to-eb.sh create               # Create environment
./deploy-to-eb.sh deploy               # Deploy updates
./deploy-to-eb.sh url                  # Get backend URL
./deploy-to-eb.sh logs                 # View logs
./deploy-to-eb.sh terminate            # Delete environment
```

## 🎉 Next Steps

After backend deployment:
1. ✅ Test all API endpoints
2. ✅ Verify Lambda functions work
3. ✅ Test Bedrock Agent integration
4. ✅ Update frontend with backend URL
5. ✅ Set up monitoring and alerts
6. ✅ Configure HTTPS (production)
7. ✅ Implement authentication (optional)

---

**Backend Status**: Ready to deploy! 🚀

For frontend setup and deployment, see [Frontend README](../frontend/README.md)
