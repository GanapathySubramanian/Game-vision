# Infrastructure & Deployment Scripts

Centralized location for all deployment and infrastructure setup scripts.

## 📁 Contents

- **`deploy.sh`** - Main infrastructure setup script (AWS resources)
- **`deploy-to-eb.sh`** - Elastic Beanstalk deployment script (backend)

## 🚀 Quick Start

### Complete Infrastructure Setup

```bash
cd bedrock-agent/infrastructure
./deploy.sh infra-setup
```

This creates:
- IAM roles for Lambda functions
- S3 bucket for video storage
- Lambda functions (video processor, analysis processor, query handler)
- Auto-generates `backend/.env` with all ARNs

### Backend Deployment to Elastic Beanstalk

```bash
cd bedrock-agent/infrastructure
./deploy-to-eb.sh init
./deploy-to-eb.sh create-role
./deploy-to-eb.sh create
```

## 📋 deploy.sh Commands

Main infrastructure management script.

### Infrastructure Commands

| Command | Description |
|---------|-------------|
| `./deploy.sh infra-setup` | **Main command** - Creates complete AWS infrastructure |
| `./deploy.sh infra-cleanup` | Deletes all AWS resources (with confirmation) |
| `./deploy.sh deploy-lambda` | Re-deploy Lambda functions only |
| `./deploy.sh create-roles` | Create IAM roles only |
| `./deploy.sh create-bucket` | Create S3 bucket only |

### Application Commands

| Command | Description |
|---------|-------------|
| `./deploy.sh setup` | Install Python/Node dependencies |
| `./deploy.sh start --dev` | Start backend + frontend dev server |
| `./deploy.sh start` | Start backend only |
| `./deploy.sh stop` | Stop all services |
| `./deploy.sh status` | Check service status |

### Usage Examples

```bash
# Complete setup (run once)
./deploy.sh infra-setup
./deploy.sh setup
./deploy.sh start --dev

# Daily development
./deploy.sh stop
./deploy.sh start --dev

# Update Lambda functions
./deploy.sh deploy-lambda

# Clean up everything
./deploy.sh infra-cleanup
```

## 📋 deploy-to-eb.sh Commands

Elastic Beanstalk deployment automation script.

### Commands

| Command | Description |
|---------|-------------|
| `./deploy-to-eb.sh init` | Initialize EB application |
| `./deploy-to-eb.sh create-role` | Create IAM instance profile for EB |
| `./deploy-to-eb.sh create` | Create EB environment |
| `./deploy-to-eb.sh deploy` | Deploy code updates |
| `./deploy-to-eb.sh status` | Check environment status |
| `./deploy-to-eb.sh logs` | View application logs |
| `./deploy-to-eb.sh url` | Get backend URL |
| `./deploy-to-eb.sh open` | Open in browser |
| `./deploy-to-eb.sh ssh` | SSH into instance |
| `./deploy-to-eb.sh terminate` | Delete environment |
| `./deploy-to-eb.sh package` | Create deployment package |

### Usage Examples

```bash
# Initial deployment
./deploy-to-eb.sh init
./deploy-to-eb.sh create-role
./deploy-to-eb.sh create

# Get backend URL
./deploy-to-eb.sh url

# Deploy updates
./deploy-to-eb.sh deploy

# View logs
./deploy-to-eb.sh logs

# Cleanup
./deploy-to-eb.sh terminate
```

## 🔧 Prerequisites

### For deploy.sh

- **AWS CLI** configured with credentials
- **Python 3.11+** and pip
- **Node.js 16+** and npm (for frontend)
- AWS permissions for:
  - IAM (create roles)
  - S3 (create buckets)
  - Lambda (create/update functions)

### For deploy-to-eb.sh

- **EB CLI** installed: `pip install awsebcli`
- **AWS CLI** configured
- AWS permissions for:
  - Elastic Beanstalk
  - EC2
  - IAM
  - CloudFormation

## 📝 Workflow

### Initial Setup

1. **Set up AWS infrastructure:**
   ```bash
   ./deploy.sh infra-setup
   ```

2. **Create Bedrock Agent** (manual step in AWS Console)
   - Use configuration from `backend/bedrock-agent/agent_config.json`
   - Connect Lambda functions as action groups
   - Note Agent ID and Alias ID

3. **Update environment variables:**
   ```bash
   # Edit backend/.env
   BEDROCK_AGENT_ID=your-agent-id
   BEDROCK_AGENT_ALIAS_ID=your-alias-id
   ```

4. **Deploy backend to EB:**
   ```bash
   ./deploy-to-eb.sh init
   ./deploy-to-eb.sh create-role
   ./deploy-to-eb.sh create
   ```

5. **Get backend URL and update frontend:**
   ```bash
   ./deploy-to-eb.sh url
   # Update frontend/.env.production with this URL
   ```

### Development Workflow

```bash
# Start local development
./deploy.sh start --dev

# Make changes to code

# Update Lambda functions if needed
./deploy.sh deploy-lambda

# Deploy backend updates to EB
./deploy-to-eb.sh deploy

# Frontend auto-deploys via Amplify on git push
```

### Cleanup

```bash
# Remove EB environment
./deploy-to-eb.sh terminate

# Remove all AWS infrastructure
./deploy.sh infra-cleanup
```

## 🐛 Troubleshooting

### deploy.sh Issues

**Issue: "Invalid principal in policy"**
- The script creates IAM roles before referencing them
- Wait a few seconds for IAM propagation if you see this error

**Issue: "Block Public Access" warning**
- This is expected and safe
- Your AWS account has S3 Block Public Access enabled (good security)
- Presigned URLs will still work

**Issue: Lambda deployment fails**
```bash
# Check IAM role exists
aws iam get-role --role-name GameplayAnalysisLambdaRole

# Redeploy Lambda functions
./deploy.sh deploy-lambda
```

### deploy-to-eb.sh Issues

**Issue: EB CLI not found**
```bash
pip install awsebcli --upgrade --user
export PATH=$PATH:~/.local/bin
```

**Issue: Environment creation fails**
```bash
# Check logs
./deploy-to-eb.sh logs

# Verify IAM role exists
aws iam get-role --role-name gameplay-analysis-eb-role
```

**Issue: Application not starting**
```bash
# SSH into instance
./deploy-to-eb.sh ssh

# Check logs
sudo tail -f /var/log/eb-engine.log
sudo tail -f /var/log/web.stdout.log
```

## 📊 What Gets Created

### By deploy.sh

**AWS Resources:**
- S3 Bucket: `gameplay-analysis-videos-[timestamp]`
- IAM Role: `GameplayAnalysisLambdaRole`
- Lambda Functions:
  - `gameplay-video-processor`
  - `gameplay-analysis-processor`
  - `gameplay-query-handler`

**Generated Files:**
- `backend/.env` - Auto-configured with all AWS resource ARNs
- `lambda-functions/*.zip` - Packaged Lambda functions

### By deploy-to-eb.sh

**AWS Resources:**
- EB Application: `gameplay-analysis-backend`
- EB Environment: `gameplay-analysis-env`
- EC2 Instance: t3.small (configurable)
- IAM Instance Profile: `gameplay-analysis-eb-role`
- Security Groups (auto-created)
- Load Balancer (optional)

**Generated Files:**
- `backend/backend-deployment.zip` - EB deployment package
- `.elasticbeanstalk/config.yml` - EB configuration

## 💰 Cost Implications

### Infrastructure (deploy.sh)
- **S3**: ~$1-3/month (storage + requests)
- **Lambda**: ~$1-5/month (pay per invocation)
- **Total**: ~$2-8/month

### Backend Deployment (deploy-to-eb.sh)
- **EB Instance**: ~$15/month (t3.small)
- **Data Transfer**: ~$1-5/month
- **Total**: ~$16-20/month

### Combined Monthly Cost
- **Development**: ~$20-30/month
- **Production**: ~$50-150/month (with auto-scaling)

## 🔒 Security Notes

- Scripts never commit sensitive data to Git
- `.env` files are excluded via `.gitignore`
- IAM roles follow principle of least privilege
- S3 buckets use account-level permissions (not public)
- Presigned URLs have short expiration times

## 📚 Additional Resources

- [Backend README](../backend/README.md) - Detailed backend documentation
- [Frontend README](../frontend/README.md) - Detailed frontend documentation
- [Root README](../README.md) - Project overview

## 🆘 Support

For issues:
1. Check script output for error messages
2. Verify AWS CLI configuration: `aws sts get-caller-identity`
3. Check AWS service quotas and limits
4. Review CloudWatch logs for Lambda/EB errors
5. Consult individual README files for detailed guides

---

**Infrastructure Status**: Ready to deploy! 🚀
