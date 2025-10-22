#!/bin/bash

# Complete Build and Push Script for Optimized Docker Image
# This script builds the optimized image and pushes it to ECR with retry logic

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Optimized Docker Build & Push${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Configuration
REGION="${AWS_REGION:-us-east-1}"
REPOSITORY_NAME="gameplay-analysis-backend"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="${ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPOSITORY_NAME}"

echo -e "${GREEN}Configuration:${NC}"
echo "  AWS Region: ${REGION}"
echo "  AWS Account: ${ACCOUNT_ID}"
echo "  ECR Repository: ${ECR_URI}"
echo ""

# Step 1: Build optimized Docker image
echo -e "${YELLOW}Step 1: Building optimized Docker image...${NC}"
echo "  - Using multi-stage build"
echo "  - Removed unused packages (asyncio-mqtt, pytest, httpx)"
echo "  - Using .dockerignore to exclude unnecessary files"
echo ""

cd ../backend

if docker build -t gameplay-analysis-backend:latest -t ${ECR_URI}:latest .; then
    echo -e "${GREEN}✓ Docker build successful${NC}"
else
    echo -e "${RED}✗ Docker build failed${NC}"
    exit 1
fi

echo ""

# Step 2: Check image size
echo -e "${YELLOW}Step 2: Checking image size...${NC}"
IMAGE_SIZE=$(docker images gameplay-analysis-backend:latest --format "{{.Size}}")
echo "  New image size: ${IMAGE_SIZE}"
echo "  Previous size: 434MB"
echo ""

# Step 3: Run the retry push script
echo -e "${YELLOW}Step 3: Pushing to ECR with retry logic...${NC}"
echo ""

cd ../infrastructure
./push-to-ecr-retry.sh

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Build and Push Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Next steps:"
echo "  1. Deploy to ECS: ./deploy-to-ecs.sh deploy"
echo "  2. Get ALB URL: ./deploy-to-ecs.sh url"
echo "  3. Update frontend .env.production with the ALB URL"
echo ""
