#!/bin/bash

# Frontend Build Script for Gameplay Analysis Application
# This script builds the React frontend and creates a deployment zip

set -e  # Exit on error

echo "=================================="
echo "Frontend Build Script"
echo "=================================="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [ ! -f "frontend/package.json" ]; then
    echo -e "${RED}Error: Must run this script from the bedrock-agent directory${NC}"
    echo "Current directory: $(pwd)"
    exit 1
fi

# Navigate to frontend directory
cd frontend

echo "Step 1: Checking prerequisites..."
echo "-----------------------------------"

# Check Node.js
if ! command -v node &> /dev/null; then
    echo -e "${RED}Error: Node.js is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Node.js version: $(node --version)${NC}"

# Check npm
if ! command -v npm &> /dev/null; then
    echo -e "${RED}Error: npm is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ npm version: $(npm --version)${NC}"

# Check zip
if ! command -v zip &> /dev/null; then
    echo -e "${RED}Error: zip utility is not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ zip utility is available${NC}"

echo ""
echo "Step 2: Checking environment configuration..."
echo "-----------------------------------------------"

# Check if .env.production exists
if [ ! -f ".env.production" ]; then
    echo -e "${RED}Error: .env.production file not found${NC}"
    exit 1
fi

# Display current API URL
API_URL=$(grep REACT_APP_API_URL .env.production | cut -d '=' -f2)
echo -e "${GREEN}✓ .env.production found${NC}"
echo "  API URL: $API_URL"

# Warn if using localhost
if [[ $API_URL == *"localhost"* ]]; then
    echo -e "${YELLOW}⚠ Warning: API URL is set to localhost. This won't work in production!${NC}"
    echo "  Update REACT_APP_API_URL in .env.production to your CloudFront URL"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""
echo "Step 3: Installing dependencies..."
echo "-----------------------------------"
npm install

echo ""
echo "Step 4: Building production bundle..."
echo "--------------------------------------"
npm run build

# Check if build was successful
if [ ! -d "build" ]; then
    echo -e "${RED}Error: Build directory not created${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Build completed successfully${NC}"

echo ""
echo "Step 5: Creating deployment zip..."
echo "-----------------------------------"

# Remove old zip if exists
if [ -f "frontend-build.zip" ]; then
    rm frontend-build.zip
    echo "Removed old frontend-build.zip"
fi

# Create zip from build directory
cd build
zip -r ../frontend-build.zip . > /dev/null 2>&1
cd ..

# Check zip was created
if [ ! -f "frontend-build.zip" ]; then
    echo -e "${RED}Error: Failed to create frontend-build.zip${NC}"
    exit 1
fi

ZIP_SIZE=$(du -h frontend-build.zip | cut -f1)
echo -e "${GREEN}✓ Created frontend-build.zip (${ZIP_SIZE})${NC}"

echo ""
echo "=================================="
echo -e "${GREEN}Build completed successfully!${NC}"
echo "=================================="
echo ""
echo "Deployment zip location:"
echo "  $(pwd)/frontend-build.zip"
echo ""
echo "Next steps:"
echo "  1. Go to AWS Amplify Console"
echo "  2. Select your app: gameplay-analysis"
echo "  3. Click 'Deploy without Git' or 'Manual deploy'"
echo "  4. Upload frontend-build.zip"
echo "  5. Wait for deployment to complete"
echo ""
echo "Your app will be available at:"
echo "  https://production.d2y1j466l93f9u.amplifyapp.com"
echo ""
