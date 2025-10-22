#!/bin/bash

# Backend Build Script for Gameplay Analysis Application
# This script creates a deployment zip for Elastic Beanstalk

set -e  # Exit on error

echo "=================================="
echo "Backend Build Script"
echo "=================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [ ! -f "backend/api_server.py" ]; then
    echo -e "${RED}Error: Must run this script from the bedrock-agent directory${NC}"
    echo "Current directory: $(pwd)"
    exit 1
fi

echo "Step 1: Checking prerequisites..."
echo "-----------------------------------"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python version: $(python3 --version)${NC}"

# Check zip
if ! command -v zip &> /dev/null; then
    echo -e "${RED}Error: zip utility is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ zip utility is available${NC}"

echo ""
echo "Step 2: Checking backend files..."
echo "----------------------------------"

# Check required files
REQUIRED_FILES=(
    "backend/api_server.py"
    "backend/requirements.txt"
    "backend/Procfile"
    "backend/.ebextensions/01_packages.config"
    "backend/.ebextensions/02_python.config"
    "backend/.ebextensions/03_nginx.config"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        echo -e "${RED}Error: Required file not found: $file${NC}"
        exit 1
    fi
    echo -e "${GREEN}✓ Found: $file${NC}"
done

echo ""
echo "Step 3: Checking environment variables..."
echo "------------------------------------------"

if [ ! -f "backend/.env" ]; then
    echo -e "${YELLOW}⚠ Warning: backend/.env file not found${NC}"
    echo "  Make sure to configure environment variables in Elastic Beanstalk console"
else
    echo -e "${GREEN}✓ .env file found${NC}"
    echo "  Note: .env is excluded from deployment (use EBS environment variables)"
fi

echo ""
echo "Step 4: Creating deployment package..."
echo "---------------------------------------"

# Create temporary directory for packaging
TEMP_DIR=$(mktemp -d)
echo "Using temporary directory: $TEMP_DIR"

# Copy backend files to temp directory
echo "Copying backend files..."
cp -r backend/* "$TEMP_DIR/"

# Remove files that shouldn't be in deployment
echo "Cleaning up unnecessary files..."
rm -rf "$TEMP_DIR/.env" 2>/dev/null || true
rm -rf "$TEMP_DIR/.env.example" 2>/dev/null || true
rm -rf "$TEMP_DIR/__pycache__" 2>/dev/null || true
rm -rf "$TEMP_DIR/*.pyc" 2>/dev/null || true
rm -rf "$TEMP_DIR/.DS_Store" 2>/dev/null || true
rm -rf "$TEMP_DIR/api_server.log" 2>/dev/null || true
rm -rf "$TEMP_DIR/bda_raw_results" 2>/dev/null || true

echo ""
echo "Step 5: Creating zip file..."
echo "----------------------------"

# Remove old zip if exists
if [ -f "backend-deploy.zip" ]; then
    rm backend-deploy.zip
    echo "Removed old backend-deploy.zip"
fi

# Create zip from temp directory
cd "$TEMP_DIR"
zip -r "$OLDPWD/backend-deploy.zip" . > /dev/null 2>&1
cd "$OLDPWD"

# Clean up temp directory
rm -rf "$TEMP_DIR"

# Check zip was created
if [ ! -f "backend-deploy.zip" ]; then
    echo -e "${RED}Error: Failed to create backend-deploy.zip${NC}"
    exit 1
fi

ZIP_SIZE=$(du -h backend-deploy.zip | cut -f1)
echo -e "${GREEN}✓ Created backend-deploy.zip (${ZIP_SIZE})${NC}"

echo ""
echo "Step 6: Verifying zip contents..."
echo "----------------------------------"
echo "Contents of backend-deploy.zip:"
unzip -l backend-deploy.zip | head -20

echo ""
echo "=================================="
echo -e "${GREEN}Build completed successfully!${NC}"
echo "=================================="
echo ""
echo "Deployment zip location:"
echo "  $(pwd)/backend-deploy.zip"
echo ""
echo "Next steps:"
echo "  1. Go to AWS Elastic Beanstalk Console"
echo "  2. Select your environment: game-vision"
echo "  3. Click 'Upload and deploy'"
echo "  4. Upload backend-deploy.zip"
echo "  5. Wait for deployment to complete"
echo ""
echo "IMPORTANT: Configure these environment variables in EBS:"
echo "  - AWS_REGION"
echo "  - S3_BUCKET_NAME"
echo "  - BEDROCK_AGENT_ID"
echo "  - BEDROCK_AGENT_ALIAS_ID"
echo "  - BDA_BLUEPRINT_ARN"
echo ""
echo ""
