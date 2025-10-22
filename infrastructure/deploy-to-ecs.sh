#!/bin/bash

# ECS Fargate Deployment Script for Gameplay Analysis Backend
# Usage: ./deploy-to-ecs.sh [command]

set -e

# Configuration
APP_NAME="gameplay-analysis"
REGION="us-east-1"
ECR_REPO_NAME="${APP_NAME}-backend"
CLUSTER_NAME="${APP_NAME}-cluster"
SERVICE_NAME="${APP_NAME}-service"
TASK_FAMILY="${APP_NAME}-task"
CONTAINER_NAME="${APP_NAME}-container"
CONTAINER_PORT=8000

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Get AWS account ID
get_account_id() {
    aws sts get-caller-identity --query Account --output text
}

# Create ECR repository
create_ecr_repo() {
    log_info "Creating ECR repository..."
    
    ACCOUNT_ID=$(get_account_id)
    
    if aws ecr describe-repositories --repository-names ${ECR_REPO_NAME} --region ${REGION} 2>/dev/null; then
        log_warn "ECR repository ${ECR_REPO_NAME} already exists"
    else
        aws ecr create-repository \
            --repository-name ${ECR_REPO_NAME} \
            --region ${REGION} \
            --image-scanning-configuration scanOnPush=true
        log_info "ECR repository created: ${ECR_REPO_NAME}"
    fi
    
    echo "${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO_NAME}"
}

# Build and push Docker image
build_and_push() {
    log_info "Building and pushing Docker image..."
    
    ACCOUNT_ID=$(get_account_id)
    ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO_NAME}"
    
    # Login to ECR
    log_info "Logging in to ECR..."
    aws ecr get-login-password --region ${REGION} | docker login --username AWS --password-stdin ${ECR_URI}
    
    # Build image
    log_info "Building Docker image..."
    cd ../backend
    docker build -t ${ECR_REPO_NAME}:latest .
    
    # Tag image
    docker tag ${ECR_REPO_NAME}:latest ${ECR_URI}:latest
    docker tag ${ECR_REPO_NAME}:latest ${ECR_URI}:$(date +%Y%m%d-%H%M%S)
    
    # Push image
    log_info "Pushing image to ECR..."
    docker push ${ECR_URI}:latest
    docker push ${ECR_URI}:$(date +%Y%m%d-%H%M%S)
    
    log_info "Image pushed successfully: ${ECR_URI}:latest"
    cd ../infrastructure
}

# Create ECS cluster
create_cluster() {
    log_info "Creating ECS cluster..."
    
    if aws ecs describe-clusters --clusters ${CLUSTER_NAME} --region ${REGION} --query 'clusters[0].status' --output text 2>/dev/null | grep -q "ACTIVE"; then
        log_warn "ECS cluster ${CLUSTER_NAME} already exists"
    else
        aws ecs create-cluster \
            --cluster-name ${CLUSTER_NAME} \
            --region ${REGION}
        log_info "ECS cluster created: ${CLUSTER_NAME}"
    fi
}

# Create task execution role
create_task_role() {
    log_info "Creating ECS task execution role..." >&2
    
    ROLE_NAME="ecsTaskExecutionRole-${APP_NAME}"
    
    if aws iam get-role --role-name ${ROLE_NAME} 2>/dev/null >&2; then
        log_warn "IAM role ${ROLE_NAME} already exists" >&2
    else
        # Create trust policy
        cat > /tmp/ecs-trust-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ecs-tasks.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
        
        # Create role
        aws iam create-role \
            --role-name ${ROLE_NAME} \
            --assume-role-policy-document file:///tmp/ecs-trust-policy.json
        
        # Attach policies
        aws iam attach-role-policy \
            --role-name ${ROLE_NAME} \
            --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
        
        aws iam attach-role-policy \
            --role-name ${ROLE_NAME} \
            --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
        
        aws iam attach-role-policy \
            --role-name ${ROLE_NAME} \
            --policy-arn arn:aws:iam::aws:policy/AmazonBedrockFullAccess
        
        log_info "IAM role created: ${ROLE_NAME}" >&2
        
        # Wait for role to be available
        sleep 10
    fi
    
    ACCOUNT_ID=$(get_account_id)
    echo "arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"
}

# Register task definition
register_task() {
    log_info "Registering ECS task definition..."
    
    ACCOUNT_ID=$(get_account_id)
    ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${ECR_REPO_NAME}:latest"
    TASK_ROLE_ARN=$(create_task_role)
    
    # Load environment variables from backend/.env using Python helper
    if [ -f "../backend/.env" ]; then
        log_info "Loading environment variables from .env file..."
        ENV_VARS=$(python3 parse-env-to-json.py ../backend/.env)
        
        # Validate JSON output
        if ! echo "$ENV_VARS" | python3 -m json.tool > /dev/null 2>&1; then
            log_error "Failed to parse environment variables"
            ENV_VARS="[]"
        fi
    else
        log_warn "No .env file found, using empty environment variables"
        ENV_VARS="[]"
    fi
    
    # Create task definition
    cat > /tmp/task-definition.json << EOF
{
  "family": "${TASK_FAMILY}",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "256",
  "memory": "512",
  "executionRoleArn": "${TASK_ROLE_ARN}",
  "taskRoleArn": "${TASK_ROLE_ARN}",
  "containerDefinitions": [
    {
      "name": "${CONTAINER_NAME}",
      "image": "${ECR_URI}",
      "essential": true,
      "portMappings": [
        {
          "containerPort": ${CONTAINER_PORT},
          "protocol": "tcp"
        }
      ],
      "environment": ${ENV_VARS},
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/${APP_NAME}",
          "awslogs-region": "${REGION}",
          "awslogs-stream-prefix": "ecs",
          "awslogs-create-group": "true"
        }
      },
      "healthCheck": {
        "command": ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"],
        "interval": 60,
        "timeout": 10,
        "retries": 3,
        "startPeriod": 120
      }
    }
  ]
}
EOF
    
    aws ecs register-task-definition \
        --cli-input-json file:///tmp/task-definition.json \
        --region ${REGION}
    
    log_info "Task definition registered: ${TASK_FAMILY}"
}

# Create Application Load Balancer
create_alb() {
    log_info "Creating Application Load Balancer..." >&2
    
    # Get default VPC
    VPC_ID=$(aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query 'Vpcs[0].VpcId' --output text --region ${REGION})
    
    # Get subnets
    SUBNETS=$(aws ec2 describe-subnets --filters "Name=vpc-id,Values=${VPC_ID}" --query 'Subnets[*].SubnetId' --output text --region ${REGION})
    SUBNET_IDS=$(echo $SUBNETS | tr ' ' ',')
    
    # Create security group for ALB
    SG_NAME="${APP_NAME}-alb-sg"
    SG_ID=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=${SG_NAME}" --query 'SecurityGroups[0].GroupId' --output text --region ${REGION} 2>/dev/null)
    
    if [ "$SG_ID" == "None" ] || [ -z "$SG_ID" ]; then
        SG_ID=$(aws ec2 create-security-group \
            --group-name ${SG_NAME} \
            --description "Security group for ${APP_NAME} ALB" \
            --vpc-id ${VPC_ID} \
            --region ${REGION} \
            --query 'GroupId' \
            --output text)
        
        # Allow HTTP traffic
        aws ec2 authorize-security-group-ingress \
            --group-id ${SG_ID} \
            --protocol tcp \
            --port 80 \
            --cidr 0.0.0.0/0 \
            --region ${REGION}
        
        log_info "Security group created: ${SG_ID}" >&2
    else
        log_warn "Security group already exists: ${SG_ID}" >&2
    fi
    
    # Create ALB
    ALB_NAME="${APP_NAME}-alb"
    ALB_ARN=$(aws elbv2 describe-load-balancers --names ${ALB_NAME} --query 'LoadBalancers[0].LoadBalancerArn' --output text --region ${REGION} 2>/dev/null)
    
    if [ "$ALB_ARN" == "None" ] || [ -z "$ALB_ARN" ]; then
        ALB_ARN=$(aws elbv2 create-load-balancer \
            --name ${ALB_NAME} \
            --subnets ${SUBNETS} \
            --security-groups ${SG_ID} \
            --region ${REGION} \
            --query 'LoadBalancers[0].LoadBalancerArn' \
            --output text)
        
        log_info "ALB created: ${ALB_ARN}" >&2
    else
        log_warn "ALB already exists: ${ALB_ARN}" >&2
    fi
    
    # Create target group
    TG_NAME="${APP_NAME}-tg"
    TG_ARN=$(aws elbv2 describe-target-groups --names ${TG_NAME} --query 'TargetGroups[0].TargetGroupArn' --output text --region ${REGION} 2>/dev/null)
    
    if [ "$TG_ARN" == "None" ] || [ -z "$TG_ARN" ]; then
        TG_ARN=$(aws elbv2 create-target-group \
            --name ${TG_NAME} \
            --protocol HTTP \
            --port ${CONTAINER_PORT} \
            --vpc-id ${VPC_ID} \
            --target-type ip \
            --health-check-path /health \
            --region ${REGION} \
            --query 'TargetGroups[0].TargetGroupArn' \
            --output text)
        
        log_info "Target group created: ${TG_ARN}" >&2
    else
        log_warn "Target group already exists: ${TG_ARN}" >&2
    fi
    
    # Create listener
    LISTENER_ARN=$(aws elbv2 describe-listeners --load-balancer-arn ${ALB_ARN} --query 'Listeners[0].ListenerArn' --output text --region ${REGION} 2>/dev/null)
    
    if [ "$LISTENER_ARN" == "None" ] || [ -z "$LISTENER_ARN" ]; then
        aws elbv2 create-listener \
            --load-balancer-arn ${ALB_ARN} \
            --protocol HTTP \
            --port 80 \
            --default-actions Type=forward,TargetGroupArn=${TG_ARN} \
            --region ${REGION}
        
        log_info "Listener created" >&2
    else
        log_warn "Listener already exists" >&2
    fi
    
    echo "${TG_ARN}|${SG_ID}|${VPC_ID}|${SUBNETS}"
}

# Create ECS service
create_service() {
    log_info "Creating ECS service..."
    
    # Get ALB details
    ALB_INFO=$(create_alb)
    TG_ARN=$(echo $ALB_INFO | cut -d'|' -f1)
    SG_ID=$(echo $ALB_INFO | cut -d'|' -f2)
    VPC_ID=$(echo $ALB_INFO | cut -d'|' -f3)
    SUBNETS=$(echo $ALB_INFO | cut -d'|' -f4)
    
    # Create security group for ECS tasks
    TASK_SG_NAME="${APP_NAME}-task-sg"
    TASK_SG_ID=$(aws ec2 describe-security-groups --filters "Name=group-name,Values=${TASK_SG_NAME}" --query 'SecurityGroups[0].GroupId' --output text --region ${REGION} 2>/dev/null)
    
    if [ "$TASK_SG_ID" == "None" ] || [ -z "$TASK_SG_ID" ]; then
        TASK_SG_ID=$(aws ec2 create-security-group \
            --group-name ${TASK_SG_NAME} \
            --description "Security group for ${APP_NAME} ECS tasks" \
            --vpc-id ${VPC_ID} \
            --region ${REGION} \
            --query 'GroupId' \
            --output text)
        
        # Allow traffic from ALB
        aws ec2 authorize-security-group-ingress \
            --group-id ${TASK_SG_ID} \
            --protocol tcp \
            --port ${CONTAINER_PORT} \
            --source-group ${SG_ID} \
            --region ${REGION}
        
        log_info "Task security group created: ${TASK_SG_ID}"
    else
        log_warn "Task security group already exists: ${TASK_SG_ID}"
    fi
    
    # Check if service exists
    if aws ecs describe-services --cluster ${CLUSTER_NAME} --services ${SERVICE_NAME} --region ${REGION} --query 'services[0].status' --output text 2>/dev/null | grep -q "ACTIVE"; then
        log_warn "Service ${SERVICE_NAME} already exists, updating..."
        aws ecs update-service \
            --cluster ${CLUSTER_NAME} \
            --service ${SERVICE_NAME} \
            --task-definition ${TASK_FAMILY} \
            --force-new-deployment \
            --region ${REGION}
    else
        # Create service
        aws ecs create-service \
            --cluster ${CLUSTER_NAME} \
            --service-name ${SERVICE_NAME} \
            --task-definition ${TASK_FAMILY} \
            --desired-count 1 \
            --launch-type FARGATE \
            --network-configuration "awsvpcConfiguration={subnets=[${SUBNETS// /,}],securityGroups=[${TASK_SG_ID}],assignPublicIp=ENABLED}" \
            --load-balancers "targetGroupArn=${TG_ARN},containerName=${CONTAINER_NAME},containerPort=${CONTAINER_PORT}" \
            --region ${REGION}
        
        log_info "ECS service created: ${SERVICE_NAME}"
    fi
}

# Get service URL
get_url() {
    ALB_NAME="${APP_NAME}-alb"
    ALB_DNS=$(aws elbv2 describe-load-balancers --names ${ALB_NAME} --query 'LoadBalancers[0].DNSName' --output text --region ${REGION} 2>/dev/null)
    
    if [ "$ALB_DNS" != "None" ] && [ -n "$ALB_DNS" ]; then
        echo ""
        log_info "Backend URL: http://${ALB_DNS}"
        echo ""
    else
        log_error "ALB not found"
    fi
}

# Show service status
show_status() {
    log_info "Checking service status..."
    
    aws ecs describe-services \
        --cluster ${CLUSTER_NAME} \
        --services ${SERVICE_NAME} \
        --region ${REGION} \
        --query 'services[0].{Status:status,Running:runningCount,Desired:desiredCount,Pending:pendingCount}' \
        --output table
}

# View logs
view_logs() {
    log_info "Fetching recent logs..."
    
    aws logs tail /ecs/${APP_NAME} --follow --region ${REGION}
}

# Cleanup
cleanup() {
    log_warn "This will delete all ECS resources. Are you sure? (yes/no)"
    read -r response
    
    if [ "$response" != "yes" ]; then
        log_info "Cleanup cancelled"
        return
    fi
    
    log_info "Deleting ECS service..."
    aws ecs delete-service --cluster ${CLUSTER_NAME} --service ${SERVICE_NAME} --force --region ${REGION} 2>/dev/null || true
    
    log_info "Deleting ECS cluster..."
    aws ecs delete-cluster --cluster ${CLUSTER_NAME} --region ${REGION} 2>/dev/null || true
    
    log_info "Deleting ALB..."
    ALB_ARN=$(aws elbv2 describe-load-balancers --names ${APP_NAME}-alb --query 'LoadBalancers[0].LoadBalancerArn' --output text --region ${REGION} 2>/dev/null)
    [ "$ALB_ARN" != "None" ] && aws elbv2 delete-load-balancer --load-balancer-arn ${ALB_ARN} --region ${REGION} 2>/dev/null || true
    
    log_info "Cleanup complete"
}

# Main command handler
case "$1" in
    create-repo)
        create_ecr_repo
        ;;
    build)
        build_and_push
        ;;
    create-cluster)
        create_cluster
        ;;
    register-task)
        register_task
        ;;
    create-service)
        create_service
        ;;
    deploy)
        create_ecr_repo
        build_and_push
        create_cluster
        register_task
        create_service
        get_url
        ;;
    deploy-only)
        log_info "Deploying with existing image in ECR..."
        create_cluster
        register_task
        create_service
        get_url
        ;;
    update)
        build_and_push
        register_task
        aws ecs update-service --cluster ${CLUSTER_NAME} --service ${SERVICE_NAME} --force-new-deployment --region ${REGION}
        log_info "Service updated"
        ;;
    url)
        get_url
        ;;
    status)
        show_status
        ;;
    logs)
        view_logs
        ;;
    cleanup)
        cleanup
        ;;
    *)
        echo "Usage: $0 {create-repo|build|create-cluster|register-task|create-service|deploy|deploy-only|update|url|status|logs|cleanup}"
        echo ""
        echo "Commands:"
        echo "  deploy         - Complete deployment (build, push, and deploy)"
        echo "  deploy-only    - Deploy using existing image in ECR (skip build/push)"
        echo "  update         - Update existing service with new code"
        echo "  url            - Get backend URL"
        echo "  status         - Show service status"
        echo "  logs           - View application logs"
        echo "  cleanup        - Delete all resources"
        echo ""
        echo "Individual steps:"
        echo "  create-repo    - Create ECR repository"
        echo "  build          - Build and push Docker image"
        echo "  create-cluster - Create ECS cluster"
        echo "  register-task  - Register task definition"
        echo "  create-service - Create ECS service"
        exit 1
        ;;
esac
