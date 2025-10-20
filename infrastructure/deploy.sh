#!/bin/bash

# Enhanced Deployment script for Gameplay Analysis Bedrock Agent
set -e

echo "🚀 Starting deployment of Gameplay Analysis Bedrock Agent..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PROJECT_NAME="gameplay-analysis"
BUCKET_NAME="${PROJECT_NAME}-videos-$(date +%s)"
IAM_ROLE_NAME="GameplayAnalysisLambdaRole"
DATA_AUTOMATION_PROJECT_NAME="game-video-analysis"
LAMBDA_FUNCTIONS=("video-processor" "analysis-processor" "query-handler")

# Function to print colored output
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

# Check if required tools are installed
check_dependencies() {
    print_status "Checking dependencies..."
    
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is required but not installed."
        exit 1
    fi
    
    if ! command -v node &> /dev/null; then
        print_error "Node.js is required but not installed."
        exit 1
    fi
    
    if ! command -v npm &> /dev/null; then
        print_error "npm is required but not installed."
        exit 1
    fi
    
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is required but not installed."
        exit 1
    fi
    
    print_status "All dependencies are installed."
}

# Check AWS configuration
check_aws_config() {
    print_status "Checking AWS configuration..."
    
    if ! aws sts get-caller-identity &> /dev/null; then
        print_error "AWS credentials are invalid or expired!"
        echo ""
        print_warning "Common issues and solutions:"
        echo ""
        echo "🔑 Issue: Temporary credentials missing session token"
        echo "   Your access key starts with 'ASIA' but session token is missing"
        echo "   Solution: Set all three environment variables:"
        echo "   export AWS_ACCESS_KEY_ID=your_access_key"
        echo "   export AWS_SECRET_ACCESS_KEY=your_secret_key"
        echo "   export AWS_SESSION_TOKEN=your_session_token"
        echo ""
        echo "🔑 Issue: Expired credentials"
        echo "   Solution: Refresh your credentials using one of:"
        echo "   - aws configure sso (for SSO)"
        echo "   - aws configure (for IAM user)"
        echo "   - Get new temporary credentials from AWS Console"
        echo ""
        echo "🔑 Required permissions for this deployment:"
        echo "   - Bedrock (bedrock:*)"
        echo "   - Lambda (lambda:*)"
        echo "   - S3 (s3:*)"
        echo "   - DynamoDB (dynamodb:*)"
        echo "   - IAM (iam:PassRole, iam:CreateRole, etc.)"
        echo ""
        print_error "Please fix AWS credentials and run this script again."
        exit 1
    fi
    
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
    AWS_REGION=$(aws configure get region)
    
    print_status "✅ AWS credentials are valid!"
    print_status "AWS Account ID: $AWS_ACCOUNT_ID"
    print_status "AWS Region: $AWS_REGION"
}

# Create IAM role for Lambda functions
create_iam_role() {
    print_step "Creating IAM role for Lambda functions..."
    
    # Check if role already exists
    if aws iam get-role --role-name $IAM_ROLE_NAME &> /dev/null; then
        print_warning "IAM role $IAM_ROLE_NAME already exists. Skipping creation."
        return 0
    fi
    
    # Create trust policy
    cat > /tmp/lambda-trust-policy.json << EOF
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
    
    # Create the role
    aws iam create-role \
        --role-name $IAM_ROLE_NAME \
        --assume-role-policy-document file:///tmp/lambda-trust-policy.json
    
    # Attach policies
    aws iam attach-role-policy \
        --role-name $IAM_ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
    
    aws iam attach-role-policy \
        --role-name $IAM_ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
    
    aws iam attach-role-policy \
        --role-name $IAM_ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess
    
    print_status "IAM role $IAM_ROLE_NAME created successfully."
    
    # Wait for role to propagate
    print_status "Waiting for IAM role to propagate..."
    sleep 10
}

# Create IAM role for Bedrock Data Automation
create_bedrock_data_automation_role() {
    print_step "Creating IAM role for Bedrock Data Automation..."
    
    BEDROCK_DA_ROLE_NAME="BedrockDataAutomationExecutionRole"
    
    # Check if role already exists
    if aws iam get-role --role-name $BEDROCK_DA_ROLE_NAME &> /dev/null; then
        print_warning "IAM role $BEDROCK_DA_ROLE_NAME already exists. Updating policies..."
        BEDROCK_DA_ROLE_ARN="arn:aws:iam::$AWS_ACCOUNT_ID:role/$BEDROCK_DA_ROLE_NAME"
    else
        # Create trust policy for Bedrock Data Automation with valid service principal
        cat > /tmp/bedrock-da-trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "bedrock.amazonaws.com"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "aws:SourceAccount": "$AWS_ACCOUNT_ID"
        }
      }
    }
  ]
}
EOF
        
        # Create the role
        aws iam create-role \
            --role-name $BEDROCK_DA_ROLE_NAME \
            --assume-role-policy-document file:///tmp/bedrock-da-trust-policy.json \
            --description "IAM role for Bedrock Data Automation to access S3 bucket and CloudWatch"
        
        BEDROCK_DA_ROLE_ARN="arn:aws:iam::$AWS_ACCOUNT_ID:role/$BEDROCK_DA_ROLE_NAME"
        print_status "IAM role $BEDROCK_DA_ROLE_NAME created successfully."
    fi
    
    # Create comprehensive S3 permissions policy for Bedrock Data Automation
    cat > /tmp/bedrock-da-s3-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3BucketAccess",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:GetObjectVersion",
        "s3:PutObject",
        "s3:PutObjectAcl",
        "s3:DeleteObject",
        "s3:ListBucket",
        "s3:GetBucketLocation",
        "s3:GetBucketVersioning"
      ],
      "Resource": [
        "arn:aws:s3:::$BUCKET_NAME",
        "arn:aws:s3:::$BUCKET_NAME/*"
      ]
    },
    {
      "Sid": "CloudWatchLogsAccess",
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams"
      ],
      "Resource": "arn:aws:logs:$AWS_REGION:$AWS_ACCOUNT_ID:*"
    },
    {
      "Sid": "BedrockDataAutomationAccess",
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:GetFoundationModel",
        "bedrock:ListFoundationModels"
      ],
      "Resource": "*"
    }
  ]
}
EOF
    
    # Create and attach the comprehensive policy
    aws iam put-role-policy \
        --role-name $BEDROCK_DA_ROLE_NAME \
        --policy-name BedrockDataAutomationComprehensiveAccess \
        --policy-document file:///tmp/bedrock-da-s3-policy.json
    
    print_status "Role ARN: $BEDROCK_DA_ROLE_ARN"
    print_status "Updated IAM role with comprehensive permissions."
    
    # Wait for role to propagate
    print_status "Waiting for Bedrock Data Automation role to propagate..."
    sleep 15
}

# Create S3 bucket
create_s3_bucket() {
    print_step "Creating S3 bucket..."
    
    # Check if bucket already exists
    if aws s3 ls "s3://$BUCKET_NAME" &> /dev/null; then
        print_warning "S3 bucket $BUCKET_NAME already exists. Skipping creation."
        return 0
    fi
    
    # Create bucket
    if [ "$AWS_REGION" = "us-east-1" ]; then
        aws s3 mb s3://$BUCKET_NAME
    else
        aws s3 mb s3://$BUCKET_NAME --region $AWS_REGION
    fi
    
    # Create CORS configuration
    cat > /tmp/s3-cors.json << EOF
{
  "CORSRules": [
    {
      "AllowedHeaders": ["*"],
      "AllowedMethods": ["GET", "PUT", "POST", "DELETE"],
      "AllowedOrigins": ["http://localhost:3000", "http://127.0.0.1:3000"],
      "ExposeHeaders": ["ETag"]
    }
  ]
}
EOF
    
    # Apply CORS configuration
    aws s3api put-bucket-cors \
        --bucket $BUCKET_NAME \
        --cors-configuration file:///tmp/s3-cors.json
    
    # Create enhanced bucket policy with comprehensive Bedrock Data Automation access
    cat > /tmp/s3-bucket-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowLambdaAccess",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::$AWS_ACCOUNT_ID:role/$IAM_ROLE_NAME"
      },
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:GetObjectVersion"
      ],
      "Resource": "arn:aws:s3:::$BUCKET_NAME/*"
    },
    {
      "Sid": "AllowBedrockDataAutomationRole",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::$AWS_ACCOUNT_ID:role/BedrockDataAutomationExecutionRole"
      },
      "Action": [
        "s3:GetObject",
        "s3:GetObjectVersion",
        "s3:PutObject",
        "s3:PutObjectAcl",
        "s3:DeleteObject",
        "s3:ListBucket",
        "s3:GetBucketLocation",
        "s3:GetBucketVersioning"
      ],
      "Resource": [
        "arn:aws:s3:::$BUCKET_NAME",
        "arn:aws:s3:::$BUCKET_NAME/*"
      ]
    },
    {
      "Sid": "AllowBedrockServices",
      "Effect": "Allow",
      "Principal": {
        "Service": [
          "bedrock.amazonaws.com",
          "bedrock-data-automation.amazonaws.com"
        ]
      },
      "Action": [
        "s3:GetObject",
        "s3:GetObjectVersion",
        "s3:PutObject",
        "s3:PutObjectAcl",
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": [
        "arn:aws:s3:::$BUCKET_NAME",
        "arn:aws:s3:::$BUCKET_NAME/*"
      ],
      "Condition": {
        "StringEquals": {
          "aws:SourceAccount": "$AWS_ACCOUNT_ID"
        }
      }
    },
    {
      "Sid": "AllowDataAutomationProjectAccess",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::$AWS_ACCOUNT_ID:role/BedrockDataAutomationExecutionRole"
      },
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::$BUCKET_NAME",
        "arn:aws:s3:::$BUCKET_NAME/*"
      ],
      "Condition": {
        "StringLike": {
          "aws:userid": "*:bedrock-data-automation-*"
        }
      }
    },
    {
      "Sid": "AllowAccountAccess",
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::$AWS_ACCOUNT_ID:root"
      },
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::$BUCKET_NAME",
        "arn:aws:s3:::$BUCKET_NAME/*"
      ]
    }
  ]
}
EOF
    
    # Try to apply bucket policy (skip if Block Public Access prevents it)
    if aws s3api put-bucket-policy \
        --bucket $BUCKET_NAME \
        --policy file:///tmp/s3-bucket-policy.json 2>/dev/null; then
        print_status "Bucket policy applied successfully."
    else
        print_warning "Could not apply bucket policy due to Block Public Access settings."
        print_warning "This is normal for secure AWS accounts. Presigned URLs will still work."
    fi
    
    print_status "S3 bucket $BUCKET_NAME created successfully."
}

# Package and deploy Lambda functions
deploy_lambda_functions() {
    print_step "Packaging and deploying Lambda functions..."
    
    cd backend/lambda-functions
    
    # Get IAM role ARN
    ROLE_ARN="arn:aws:iam::$AWS_ACCOUNT_ID:role/$IAM_ROLE_NAME"
    
    # Deploy video processor
    print_status "Deploying video processor Lambda..."
    zip -r video_processor.zip video_processor.py ../shared/aws_helpers.py
    
    if aws lambda get-function --function-name gameplay-video-processor &> /dev/null; then
        aws lambda update-function-code \
            --function-name gameplay-video-processor \
            --zip-file fileb://video_processor.zip
    else
        aws lambda create-function \
            --function-name gameplay-video-processor \
            --runtime python3.11 \
            --role $ROLE_ARN \
            --handler video_processor.lambda_handler \
            --zip-file fileb://video_processor.zip \
            --timeout 300 \
            --memory-size 512
    fi
    
    # Deploy analysis processor
    print_status "Deploying analysis processor Lambda..."
    zip -r analysis_processor.zip analysis_processor.py ../shared/aws_helpers.py
    
    if aws lambda get-function --function-name gameplay-analysis-processor &> /dev/null; then
        aws lambda update-function-code \
            --function-name gameplay-analysis-processor \
            --zip-file fileb://analysis_processor.zip
    else
        aws lambda create-function \
            --function-name gameplay-analysis-processor \
            --runtime python3.11 \
            --role $ROLE_ARN \
            --handler analysis_processor.lambda_handler \
            --zip-file fileb://analysis_processor.zip \
            --timeout 900 \
            --memory-size 1024
    fi
    
    # Deploy query handler
    print_status "Deploying query handler Lambda..."
    zip -r query_handler.zip query_handler.py ../shared/aws_helpers.py
    
    if aws lambda get-function --function-name gameplay-query-handler &> /dev/null; then
        aws lambda update-function-code \
            --function-name gameplay-query-handler \
            --zip-file fileb://query_handler.zip
    else
        aws lambda create-function \
            --function-name gameplay-query-handler \
            --runtime python3.11 \
            --role $ROLE_ARN \
            --handler query_handler.lambda_handler \
            --zip-file fileb://query_handler.zip \
            --timeout 300 \
            --memory-size 512
    fi
    
    cd ../..
    print_status "Lambda functions deployed successfully."
}

# Add Lambda permissions for Bedrock Agent
add_lambda_permissions() {
    print_step "Adding Lambda permissions for Bedrock Agent..."
    
    # Check if BEDROCK_AGENT_ID is provided
    if [ -f "backend/.env" ]; then
        BEDROCK_AGENT_ID=$(grep BEDROCK_AGENT_ID backend/.env | cut -d'=' -f2)
        if [ "$BEDROCK_AGENT_ID" = "your-agent-id-here" ] || [ -z "$BEDROCK_AGENT_ID" ]; then
            print_warning "BEDROCK_AGENT_ID not configured in backend/.env"
            print_warning "Please update BEDROCK_AGENT_ID in backend/.env and run: ./deploy.sh fix-permissions"
            return 0
        fi
    else
        print_error "backend/.env file not found. Run infra-setup first."
        return 1
    fi
    
    # Construct Bedrock Agent ARN
    BEDROCK_AGENT_ARN="arn:aws:bedrock:$AWS_REGION:$AWS_ACCOUNT_ID:agent/$BEDROCK_AGENT_ID"
    
    # Lambda function names
    LAMBDA_FUNCTIONS=("gameplay-video-processor" "gameplay-analysis-processor" "gameplay-query-handler")
    
    for FUNCTION_NAME in "${LAMBDA_FUNCTIONS[@]}"; do
        print_status "Adding Bedrock Agent permission to $FUNCTION_NAME..."
        
        # Remove existing permission if it exists (to avoid conflicts)
        aws lambda remove-permission \
            --function-name $FUNCTION_NAME \
            --statement-id bedrock-agent-invoke \
            2>/dev/null || true
        
        # Add new permission
        if aws lambda add-permission \
            --function-name $FUNCTION_NAME \
            --statement-id bedrock-agent-invoke \
            --action lambda:InvokeFunction \
            --principal bedrock.amazonaws.com \
            --source-arn $BEDROCK_AGENT_ARN \
            2>/dev/null; then
            print_status "✅ Permission added for $FUNCTION_NAME"
        else
            print_error "❌ Failed to add permission for $FUNCTION_NAME"
        fi
    done
    
    print_status "Lambda permissions configuration complete!"
    print_status "Bedrock Agent should now be able to invoke Lambda functions."
}

# Fix Bedrock Agent permissions (standalone command)
fix_bedrock_permissions() {
    print_step "Fixing Bedrock Agent Lambda permissions..."
    check_aws_config
    add_lambda_permissions
}

# Verify Data Automation permissions
verify_data_automation_permissions() {
    print_step "Verifying Bedrock Data Automation permissions..."
    check_aws_config
    
    cd backend
    source venv/bin/activate 2>/dev/null || {
        print_error "Python virtual environment not found. Run './deploy.sh setup' first."
        exit 1
    }
    
    python3 -c "
import asyncio
import sys
import os
sys.path.append('.')

# Load environment variables from .env file
def load_env_file():
    env_file = '.env'
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value

load_env_file()

from shared.aws_helpers import verify_data_automation_permissions
import json

async def main():
    try:
        results = await verify_data_automation_permissions()
        print(json.dumps(results, indent=2))
        
        if results['status'] == 'HEALTHY':
            print('\n✅ All permissions are properly configured!')
        elif results['status'] == 'NEEDS_ATTENTION':
            print('\n⚠️  Some issues found that need attention:')
            for issue in results['permissions_issues']:
                print(f'  - {issue}')
            print('\nRecommendations:')
            for rec in results['recommendations']:
                print(f'  - {rec}')
        else:
            print('\n❌ Critical permission issues found:')
            for issue in results['permissions_issues']:
                print(f'  - {issue}')
            print('\nRecommendations:')
            for rec in results['recommendations']:
                print(f'  - {rec}')
            print('\nRun: ./deploy.sh fix-data-automation-permissions')
            
    except Exception as e:
        print(f'Verification failed: {e}')
        sys.exit(1)

asyncio.run(main())
"
    cd ..
}

# Fix Data Automation permissions
fix_data_automation_permissions() {
    print_step "Fixing Bedrock Data Automation permissions..."
    check_aws_config
    
    cd backend
    source venv/bin/activate 2>/dev/null || {
        print_error "Python virtual environment not found. Run './deploy.sh setup' first."
        exit 1
    }
    
    python3 -c "
import asyncio
import sys
import os
sys.path.append('.')

# Load environment variables from .env file
def load_env_file():
    env_file = '.env'
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value

load_env_file()

from shared.aws_helpers import fix_data_automation_permissions
import json

async def main():
    try:
        results = await fix_data_automation_permissions()
        
        if results['actions_taken']:
            print('✅ Actions taken:')
            for action in results['actions_taken']:
                print(f'  - {action}')
        
        if results['errors']:
            print('❌ Errors encountered:')
            for error in results['errors']:
                print(f'  - {error}')
        
        if results['success']:
            print('\n🎉 Successfully fixed Data Automation permissions!')
            print('You can now test the analysis with: ./deploy.sh test-data-automation-access')
        else:
            print('\n⚠️  Permission fix completed with some issues.')
            print('Please review the errors above and fix them manually.')
            
    except Exception as e:
        print(f'Fix operation failed: {e}')
        sys.exit(1)

asyncio.run(main())
"
    cd ..
}

# Test Data Automation access
test_data_automation_access() {
    print_step "Testing Bedrock Data Automation access..."
    check_aws_config
    
    # Check if test video file is provided
    TEST_VIDEO_S3_URI="$1"
    if [ -z "$TEST_VIDEO_S3_URI" ]; then
        # Use default test video if available
        BUCKET_NAME=$(grep AWS_BUCKET_NAME backend/.env 2>/dev/null | cut -d'=' -f2)
        if [ ! -z "$BUCKET_NAME" ]; then
            TEST_VIDEO_S3_URI="s3://$BUCKET_NAME/videos/test-video.mp4"
            print_warning "No S3 URI provided. Using default: $TEST_VIDEO_S3_URI"
            print_warning "Make sure you have uploaded a test video to this location."
        else
            print_error "No S3 URI provided and bucket name not found in .env"
            print_error "Usage: ./deploy.sh test-data-automation-access s3://your-bucket/path/to/video.mp4"
            exit 1
        fi
    fi
    
    cd backend
    source venv/bin/activate 2>/dev/null || {
        print_error "Python virtual environment not found. Run './deploy.sh setup' first."
        exit 1
    }
    
    python3 -c "
import asyncio
import sys
import os
sys.path.append('.')

# Load environment variables from .env file
def load_env_file():
    env_file = '.env'
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value

load_env_file()

from shared.aws_helpers import test_data_automation_access
import json

async def main():
    try:
        s3_uri = '$TEST_VIDEO_S3_URI'
        print(f'Testing Data Automation access with: {s3_uri}')
        
        results = await test_data_automation_access(s3_uri)
        
        if results['access_test_passed']:
            print('✅ Data Automation access test PASSED!')
            print('Bedrock Data Automation can successfully access your S3 bucket and start jobs.')
            if 'test_job_arn' in results:
                print(f'Test job ARN: {results[\"test_job_arn\"]}')
        else:
            print('❌ Data Automation access test FAILED!')
            print(f'Error: {results[\"error_message\"]}')
            
            if results['recommendations']:
                print('\nRecommendations:')
                for rec in results['recommendations']:
                    print(f'  - {rec}')
                    
            print('\nTry running: ./deploy.sh fix-data-automation-permissions')
            
    except Exception as e:
        print(f'Access test failed: {e}')
        sys.exit(1)

asyncio.run(main())
"
    cd ..
}

# Create Bedrock Data Automation Project
create_data_automation_project() {
    print_step "Creating Bedrock Data Automation Project..."
    
    # Upload blueprint to S3 first
    print_status "Uploading custom game analysis blueprint to S3..."
    BLUEPRINT_S3_KEY="blueprints/game-analysis-blueprint.json"
    aws s3 cp backend/bedrock-data-automation/game-analysis-blueprint.json s3://$BUCKET_NAME/$BLUEPRINT_S3_KEY
    
    # Create the data automation project using AWS CLI
    print_status "Creating Bedrock Data Automation project: $DATA_AUTOMATION_PROJECT_NAME"
    
    # Create project configuration
    cat > /tmp/create-project-request.json << EOF
{
  "projectName": "$DATA_AUTOMATION_PROJECT_NAME",
  "description": "Multi-sport game video analysis with custom blueprint for player actions, scoring events, violations, and game context",
  "blueprintConfiguration": {
    "blueprintS3Uri": "s3://$BUCKET_NAME/$BLUEPRINT_S3_KEY"
  },
  "outputConfiguration": {
    "s3OutputConfiguration": {
      "bucketName": "$BUCKET_NAME",
      "keyPrefix": "analysis-results/"
    }
  },
  "encryptionConfiguration": {
    "kmsKeyId": "alias/aws/s3"
  }
}
EOF
    
    # Try to create the project using Bedrock Data Automation API
    if PROJECT_RESPONSE=$(aws bedrock-data-automation create-data-automation-project \
        --cli-input-json file:///tmp/create-project-request.json \
        --region $AWS_REGION 2>/dev/null); then
        
        PROJECT_ARN=$(echo $PROJECT_RESPONSE | jq -r '.projectArn')
        print_status "Successfully created Bedrock Data Automation project!"
        print_status "Project ARN: $PROJECT_ARN"
        
        # Update environment with actual project ARN
        sed -i.bak "s|DATA_AUTOMATION_PROJECT_ARN=your-project-arn-here|DATA_AUTOMATION_PROJECT_ARN=$PROJECT_ARN|" backend/.env
        
    else
        print_warning "Bedrock Data Automation API not available or project creation failed."
        print_warning "Please create the project manually in AWS Console:"
        print_warning "1. Go to Amazon Bedrock → Data Automation"
        print_warning "2. Create new project: '$DATA_AUTOMATION_PROJECT_NAME'"
        print_warning "3. Upload blueprint from: backend/bedrock-data-automation/game-analysis-blueprint.json"
        print_warning "4. Set output bucket: $BUCKET_NAME"
        print_warning "5. Update DATA_AUTOMATION_PROJECT_ARN in backend/.env"
        
        # Store project configuration for manual reference
        cat > /tmp/data-automation-config.json << EOF
{
  "projectName": "$DATA_AUTOMATION_PROJECT_NAME",
  "description": "Multi-sport game video analysis with custom blueprint for player actions, scoring events, violations, and game context",
  "blueprintPath": "backend/bedrock-data-automation/game-analysis-blueprint.json",
  "blueprintS3Uri": "s3://$BUCKET_NAME/$BLUEPRINT_S3_KEY",
  "outputBucket": "$BUCKET_NAME",
  "outputPrefix": "analysis-results/",
  "region": "$AWS_REGION"
}
EOF
        
        print_status "Manual setup configuration saved to /tmp/data-automation-config.json"
    fi
}

# Generate environment configuration
generate_env_config() {
    print_step "Generating environment configuration..."
    
    # Create .env file
    cat > backend/.env << EOF
# AWS Configuration
AWS_REGION=$AWS_REGION
AWS_BUCKET_NAME=$BUCKET_NAME

# Bedrock Agent Configuration (to be filled manually)
BEDROCK_AGENT_ID=your-agent-id-here
BEDROCK_AGENT_ALIAS_ID=your-agent-alias-id-here

# Bedrock Data Automation Configuration
DATA_AUTOMATION_PROJECT_NAME=$DATA_AUTOMATION_PROJECT_NAME
DATA_AUTOMATION_PROJECT_ARN=your-project-arn-here

# Lambda Function ARNs
VIDEO_PROCESSOR_ARN=arn:aws:lambda:$AWS_REGION:$AWS_ACCOUNT_ID:function:gameplay-video-processor
ANALYSIS_PROCESSOR_ARN=arn:aws:lambda:$AWS_REGION:$AWS_ACCOUNT_ID:function:gameplay-analysis-processor
QUERY_HANDLER_ARN=arn:aws:lambda:$AWS_REGION:$AWS_ACCOUNT_ID:function:gameplay-query-handler

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
EOF
    
    print_status "Environment configuration generated in backend/.env"
    print_warning "Please update BEDROCK_AGENT_ID, BEDROCK_AGENT_ALIAS_ID, and DATA_AUTOMATION_PROJECT_ARN after creating resources."
}

# Setup AWS infrastructure
setup_aws_infrastructure() {
    print_status "Setting up AWS infrastructure..."
    
    check_aws_config
    create_iam_role
    create_bedrock_data_automation_role
    create_s3_bucket
    create_data_automation_project
    deploy_lambda_functions
    generate_env_config
    
    # Try to add Lambda permissions if Bedrock Agent ID is already configured
    print_step "Checking for Bedrock Agent configuration..."
    if [ -f "backend/.env" ]; then
        BEDROCK_AGENT_ID=$(grep BEDROCK_AGENT_ID backend/.env | cut -d'=' -f2)
        if [ "$BEDROCK_AGENT_ID" != "your-agent-id-here" ] && [ ! -z "$BEDROCK_AGENT_ID" ]; then
            print_status "Bedrock Agent ID found, adding Lambda permissions..."
            add_lambda_permissions
        else
            print_warning "Bedrock Agent ID not configured yet."
            print_warning "After creating your Bedrock Agent, update BEDROCK_AGENT_ID in backend/.env"
            print_warning "Then run: ./deploy.sh add-permissions"
        fi
    fi
    
    print_status "AWS infrastructure setup complete!"
    echo ""
    print_status "📋 Next Steps:"
    echo "1. Create Bedrock Data Automation Blueprint:"
    echo "   📖 Follow the detailed guide: BLUEPRINT_CREATION_GUIDE.md"
    echo "   🎯 Use your custom output data to generate the blueprint"
    echo "   📁 Project name: '$DATA_AUTOMATION_PROJECT_NAME'"
    echo "   🪣 Output bucket: $BUCKET_NAME"
    echo ""
    echo "2. Create Bedrock Agent in AWS Console:"
    echo "   📄 Use configuration: backend/bedrock-agent/agent_config.json"
    echo ""
    echo "3. Update Environment Variables in backend/.env:"
    echo "   🔑 BEDROCK_AGENT_ID=your-agent-id"
    echo "   🔑 BEDROCK_AGENT_ALIAS_ID=your-alias-id"
    echo "   🔑 DATA_AUTOMATION_PROJECT_ARN=your-project-arn"
    echo ""
    echo "4. Install and Start Application:"
    echo "   📦 ./deploy.sh setup"
    echo "   🚀 ./deploy.sh start --dev"
    echo ""
    print_status "📊 Created Resources:"
    echo "- S3 Bucket: $BUCKET_NAME"
    echo "- IAM Role: $IAM_ROLE_NAME"
    echo "- Lambda Functions: gameplay-video-processor, gameplay-analysis-processor, gameplay-query-handler"
    echo "- Data Automation Config: /tmp/data-automation-config.json"
    echo ""
    print_status "🎯 Custom Hockey Analysis Features:"
    echo "- Player action detection (goals, assists, saves, hits)"
    echo "- Game event analysis (penalties, fights, celebrations)"
    echo "- Spectator reaction analysis (cheering, booing, standing)"
    echo "- Scene detection (locker room, team bus, interviews)"
    echo "- Temporal segmentation with SMPTE timecodes"
    echo "- Multi-modal analysis (video, audio, text extraction)"
}

# Clean up AWS resources
cleanup_aws_infrastructure() {
    print_warning "This will delete all AWS resources created by this script."
    read -p "Are you sure you want to continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_status "Cleanup cancelled."
        return 0
    fi
    
    print_step "Cleaning up AWS infrastructure..."
    
    # Delete Lambda functions
    for func in "${LAMBDA_FUNCTIONS[@]}"; do
        if aws lambda get-function --function-name "gameplay-$func" &> /dev/null; then
            aws lambda delete-function --function-name "gameplay-$func"
            print_status "Deleted Lambda function: gameplay-$func"
        fi
    done
    
    # Delete S3 bucket (if we know the name)
    if [ -f "backend/.env" ]; then
        BUCKET_NAME=$(grep AWS_BUCKET_NAME backend/.env | cut -d'=' -f2)
        if [ ! -z "$BUCKET_NAME" ]; then
            aws s3 rm s3://$BUCKET_NAME --recursive
            aws s3 rb s3://$BUCKET_NAME
            print_status "Deleted S3 bucket: $BUCKET_NAME"
        fi
    fi
    
    # Delete IAM role
    if aws iam get-role --role-name $IAM_ROLE_NAME &> /dev/null; then
        # Detach policies
        aws iam detach-role-policy --role-name $IAM_ROLE_NAME --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
        aws iam detach-role-policy --role-name $IAM_ROLE_NAME --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
        aws iam detach-role-policy --role-name $IAM_ROLE_NAME --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess
        
        # Delete role
        aws iam delete-role --role-name $IAM_ROLE_NAME
        print_status "Deleted IAM role: $IAM_ROLE_NAME"
    fi
    
    print_status "AWS infrastructure cleanup complete."
}

# Setup backend
setup_backend() {
    print_status "Setting up backend..."
    
    cd backend
    
    # Create virtual environment if it doesn't exist
    if [ ! -d "venv" ]; then
        print_status "Creating Python virtual environment..."
        python3 -m venv venv
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Install Python dependencies
    print_status "Installing Python dependencies..."
    pip install -r requirements.txt
    
    # Check if .env file exists
    if [ ! -f ".env" ]; then
        print_warning ".env file not found. Please copy .env.example to .env and configure it."
        cp .env.example .env
    fi
    
    cd ..
    print_status "Backend setup complete."
}

# Setup frontend
setup_frontend() {
    print_status "Setting up frontend..."
    
    cd frontend
    
    # Install Node.js dependencies
    print_status "Installing Node.js dependencies..."
    npm install
    
    # Build the frontend
    print_status "Building frontend..."
    npm run build
    
    cd ..
    print_status "Frontend setup complete."
}

# Deploy Bedrock Agent (placeholder)
deploy_bedrock_agent() {
    print_status "Deploying Bedrock Agent..."
    print_warning "Bedrock Agent deployment requires manual setup through AWS Console or CDK."
    print_warning "Please refer to the documentation for detailed instructions."
}

# Start services
start_services() {
    print_status "Starting services..."
    
    # Start backend API server
    print_status "Starting backend API server..."
    cd backend
    source venv/bin/activate
    nohup python api_server.py > api_server.log 2>&1 &
    BACKEND_PID=$!
    echo $BACKEND_PID > backend.pid
    cd ..
    
    # Start frontend development server (optional)
    if [ "$1" = "--dev" ]; then
        print_status "Starting frontend development server..."
        cd frontend
        nohup npm start > frontend.log 2>&1 &
        FRONTEND_PID=$!
        echo $FRONTEND_PID > frontend.pid
        cd ..
        
        print_status "Frontend development server started at http://localhost:3000"
    fi
    
    print_status "Backend API server started at http://localhost:8000"
    print_status "Services started successfully!"
}

# Stop services
stop_services() {
    print_status "Stopping services..."
    
    # Stop backend
    if [ -f "backend/backend.pid" ]; then
        BACKEND_PID=$(cat backend/backend.pid)
        if ps -p $BACKEND_PID > /dev/null; then
            kill $BACKEND_PID
            print_status "Backend API server stopped."
        fi
        rm backend/backend.pid
    fi
    
    # Stop frontend
    if [ -f "frontend/frontend.pid" ]; then
        FRONTEND_PID=$(cat frontend/frontend.pid)
        if ps -p $FRONTEND_PID > /dev/null; then
            kill $FRONTEND_PID
            print_status "Frontend development server stopped."
        fi
        rm frontend/frontend.pid
    fi
    
    print_status "All services stopped."
}

# Main deployment logic
case "$1" in
    "infra-setup")
        check_dependencies
        setup_aws_infrastructure
        ;;
    "infra-cleanup")
        cleanup_aws_infrastructure
        ;;
    "deploy-lambda")
        check_dependencies
        check_aws_config
        deploy_lambda_functions
        ;;
    "create-roles")
        check_dependencies
        check_aws_config
        create_iam_role
        ;;
    "create-bucket")
        check_dependencies
        check_aws_config
        create_s3_bucket
        ;;
    "create-data-automation")
        check_dependencies
        check_aws_config
        create_data_automation_project
        ;;
    "add-permissions")
        fix_bedrock_permissions
        ;;
    "setup")
        check_dependencies
        setup_backend
        setup_frontend
        deploy_bedrock_agent
        print_status "Setup complete! Run './deploy.sh start' to start services."
        ;;
    "start")
        start_services $2
        ;;
    "stop")
        stop_services
        ;;
    "restart")
        stop_services
        sleep 2
        start_services $2
        ;;
    "status")
        print_status "Checking service status..."
        
        # Check backend
        if [ -f "backend/backend.pid" ]; then
            BACKEND_PID=$(cat backend/backend.pid)
            if ps -p $BACKEND_PID > /dev/null; then
                print_status "Backend API server is running (PID: $BACKEND_PID)"
            else
                print_warning "Backend API server is not running"
            fi
        else
            print_warning "Backend API server is not running"
        fi
        
        # Check frontend
        if [ -f "frontend/frontend.pid" ]; then
            FRONTEND_PID=$(cat frontend/frontend.pid)
            if ps -p $FRONTEND_PID > /dev/null; then
                print_status "Frontend development server is running (PID: $FRONTEND_PID)"
            else
                print_warning "Frontend development server is not running"
            fi
        else
            print_warning "Frontend development server is not running"
        fi
        ;;
    "verify-data-automation-permissions")
        verify_data_automation_permissions
        ;;
    "fix-data-automation-permissions")
        fix_data_automation_permissions
        ;;
    "test-data-automation-access")
        test_data_automation_access $2
        ;;
    *)
        echo "Usage: $0 {infra-setup|infra-cleanup|deploy-lambda|create-roles|create-bucket|create-data-automation|add-permissions|setup|start|stop|restart|status|verify-data-automation-permissions|fix-data-automation-permissions|test-data-automation-access}"
        echo ""
        echo "🏗️  Infrastructure Commands:"
        echo "  infra-setup          - Create complete AWS infrastructure (S3, IAM, Lambda, Data Automation)"
        echo "  infra-cleanup        - Delete all AWS resources created by this script"
        echo "  deploy-lambda        - Package and deploy Lambda functions only"
        echo "  create-roles         - Create IAM roles only"
        echo "  create-bucket        - Create S3 bucket only"
        echo "  create-data-automation - Create Bedrock Data Automation project config only"
        echo "  add-permissions      - Add Lambda permissions for Bedrock Agent (run after setting BEDROCK_AGENT_ID)"
        echo ""
        echo "🔧 Diagnostic & Fix Commands:"
        echo "  verify-data-automation-permissions - Check Data Automation permissions and configuration"
        echo "  fix-data-automation-permissions    - Automatically fix common permission issues"
        echo "  test-data-automation-access [s3_uri] - Test Data Automation access with a video file"
        echo ""
        echo "🚀 Application Commands:"
        echo "  setup               - Install dependencies and setup the project"
        echo "  start               - Start the services (add --dev to start frontend dev server)"
        echo "  stop                - Stop all services"
        echo "  restart             - Restart all services"
        echo "  status              - Check service status"
        echo ""
        echo "📋 Quick Start:"
        echo "  1. $0 infra-setup        # Create AWS infrastructure + Data Automation config"
        echo "  2. $0 setup              # Install app dependencies"
        echo "  3. $0 start --dev        # Start application"
        echo ""
        echo "🔍 Troubleshooting AccessDenied Errors:"
        echo "  1. $0 verify-data-automation-permissions  # Check current permissions"
        echo "  2. $0 fix-data-automation-permissions     # Fix permission issues"
        echo "  3. $0 test-data-automation-access         # Test with a video file"
        echo ""
        echo "🎯 Custom Hockey Analysis:"
        echo "  - Player actions (goals, assists, saves, hits, passes, shots)"
        echo "  - Game events (penalties, fights, timeouts, celebrations)"
        echo "  - Spectator reactions (cheering, booing, standing, waving)"
        echo "  - Scene detection (locker room, team bus, interviews)"
        echo "  - SMPTE timecode precision with frame-level analysis"
        echo ""
        echo "🧹 Cleanup:"
        echo "  $0 infra-cleanup         # Remove all AWS resources"
        exit 1
        ;;
esac
