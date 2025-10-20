#!/bin/bash

# Quick deployment script for AWS Elastic Beanstalk
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Check if EB CLI is installed
if ! command -v eb &> /dev/null; then
    print_error "EB CLI is not installed!"
    echo ""
    echo "Install it with:"
    echo "  pip install awsebcli --upgrade --user"
    echo ""
    exit 1
fi

print_status "EB CLI is installed: $(eb --version)"

# Check if we're in the backend directory
if [ ! -f "api_server.py" ]; then
    print_error "Please run this script from the backend directory!"
    echo "  cd bedrock-agent/backend"
    exit 1
fi

# Main deployment logic
case "$1" in
    "init")
        print_step "Initializing Elastic Beanstalk application..."
        eb init -p python-3.11 gameplay-analysis-backend --region us-east-1
        print_status "✅ EB application initialized!"
        echo ""
        print_status "Next steps:"
        echo "  1. Create IAM role: ./deploy-to-eb.sh create-role"
        echo "  2. Create environment: ./deploy-to-eb.sh create"
        ;;
    
    "create-role")
        print_step "Creating IAM role for EB instances..."
        
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
        if aws iam create-role \
            --role-name gameplay-analysis-eb-role \
            --assume-role-policy-document file:///tmp/eb-trust-policy.json 2>/dev/null; then
            print_status "✅ IAM role created"
        else
            print_warning "IAM role may already exist, continuing..."
        fi
        
        # Attach policies
        print_status "Attaching policies..."
        aws iam attach-role-policy \
            --role-name gameplay-analysis-eb-role \
            --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess 2>/dev/null || true
        
        aws iam attach-role-policy \
            --role-name gameplay-analysis-eb-role \
            --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess 2>/dev/null || true
        
        aws iam attach-role-policy \
            --role-name gameplay-analysis-eb-role \
            --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaRole 2>/dev/null || true
        
        aws iam attach-role-policy \
            --role-name gameplay-analysis-eb-role \
            --policy-arn arn:aws:iam::aws:policy/CloudWatchLogsFullAccess 2>/dev/null || true
        
        # Create instance profile
        if aws iam create-instance-profile \
            --instance-profile-name gameplay-analysis-eb-role 2>/dev/null; then
            print_status "✅ Instance profile created"
        else
            print_warning "Instance profile may already exist, continuing..."
        fi
        
        # Add role to instance profile
        aws iam add-role-to-instance-profile \
            --instance-profile-name gameplay-analysis-eb-role \
            --role-name gameplay-analysis-eb-role 2>/dev/null || true
        
        print_status "✅ IAM role setup complete!"
        echo ""
        print_status "Next step:"
        echo "  ./deploy-to-eb.sh create"
        ;;
    
    "create")
        print_step "Creating Elastic Beanstalk environment..."
        print_warning "This will take 5-10 minutes..."
        
        eb create gameplay-analysis-env \
            --instance-type t3.small \
            --instance-profile gameplay-analysis-eb-role \
            --region us-east-1
        
        print_status "✅ Environment created!"
        echo ""
        print_status "Get your URL with:"
        echo "  ./deploy-to-eb.sh url"
        ;;
    
    "deploy")
        print_step "Deploying application to Elastic Beanstalk..."
        eb deploy
        print_status "✅ Deployment complete!"
        echo ""
        print_status "Check status with:"
        echo "  ./deploy-to-eb.sh status"
        ;;
    
    "status")
        print_step "Checking environment status..."
        eb status
        ;;
    
    "logs")
        print_step "Fetching logs..."
        eb logs
        ;;
    
    "url")
        print_step "Getting application URL..."
        URL=$(eb status | grep "CNAME" | awk '{print $2}')
        if [ ! -z "$URL" ]; then
            print_status "Your backend URL: http://$URL"
            echo ""
            print_status "Test it with:"
            echo "  curl http://$URL/health"
            echo ""
            print_status "Update your frontend .env with:"
            echo "  REACT_APP_API_URL=http://$URL"
        else
            print_error "Could not find URL. Is the environment created?"
        fi
        ;;
    
    "open")
        print_step "Opening application in browser..."
        eb open
        ;;
    
    "ssh")
        print_step "Connecting to instance via SSH..."
        eb ssh
        ;;
    
    "terminate")
        print_warning "This will DELETE your Elastic Beanstalk environment!"
        read -p "Are you sure? (yes/no): " -r
        if [[ $REPLY == "yes" ]]; then
            print_step "Terminating environment..."
            eb terminate gameplay-analysis-env --force
            print_status "✅ Environment terminated"
        else
            print_status "Cancelled"
        fi
        ;;
    
    "package")
        print_step "Creating deployment package..."
        zip -r backend-deployment.zip . \
            -x "venv/*" \
            -x "__pycache__/*" \
            -x "*.pyc" \
            -x ".env" \
            -x "*.log" \
            -x "bda_raw_results/*" \
            -x ".git/*" \
            -x "*.zip"
        
        print_status "✅ Package created: backend-deployment.zip"
        echo ""
        print_status "Upload this to AWS Console or use:"
        echo "  ./deploy-to-eb.sh deploy"
        ;;
    
    *)
        echo "Usage: $0 {init|create-role|create|deploy|status|logs|url|open|ssh|terminate|package}"
        echo ""
        echo "🚀 Quick Start (First Time):"
        echo "  1. ./deploy-to-eb.sh init          # Initialize EB application"
        echo "  2. ./deploy-to-eb.sh create-role   # Create IAM role"
        echo "  3. ./deploy-to-eb.sh create        # Create environment (5-10 min)"
        echo "  4. ./deploy-to-eb.sh url           # Get your backend URL"
        echo ""
        echo "📦 Deployment Commands:"
        echo "  deploy      - Deploy/update application"
        echo "  package     - Create deployment ZIP for manual upload"
        echo ""
        echo "🔍 Monitoring Commands:"
        echo "  status      - Check environment status"
        echo "  logs        - View application logs"
        echo "  url         - Get application URL"
        echo "  open        - Open app in browser"
        echo ""
        echo "🛠️ Management Commands:"
        echo "  ssh         - SSH into instance"
        echo "  terminate   - Delete environment"
        echo ""
        exit 1
        ;;
esac
