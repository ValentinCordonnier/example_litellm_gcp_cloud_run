#!/bin/bash

# LiteLLM GCP Cloud Run Deployment Script
# This script builds and deploys LiteLLM to Google Cloud Run

set -e

# Configuration
PROJECT_ID="${VERTEXAI_PROJECT:-your-gcp-project-id}"
REGION="${VERTEXAI_LOCATION:-us-central1}"
SERVICE_NAME="litellm-gateway"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting deployment of LiteLLM to Cloud Run${NC}"

# Check if required environment variables are set
if [ -z "$LITELLM_MASTER_KEY" ]; then
    echo -e "${RED}Error: Required environment variables not set${NC}"
    echo "Please set: LITELLM_MASTER_KEY"
    echo "You can source them from a .env file: source .env"
    exit 1
fi

# Extract Cloud SQL connection name from DATABASE_URL if present
CLOUD_SQL_CONNECTION=""
if [ ! -z "$DATABASE_URL" ]; then
    # Extract connection string like: hack-ai-unified-ai-platform:europe-west1:lite-llm-bdd
    # Works on both macOS and Linux
    CLOUD_SQL_CONNECTION=$(echo "$DATABASE_URL" | sed -n 's/.*cloudsql\/\([^)]*\).*/\1/p')
    if [ ! -z "$CLOUD_SQL_CONNECTION" ]; then
        echo -e "${GREEN}Using Cloud SQL connection: ${CLOUD_SQL_CONNECTION}${NC}"
    fi
fi

# Step 1: Build the container image
echo -e "${YELLOW}Building container image...${NC}"
gcloud builds submit --tag ${IMAGE_NAME} .

# Step 2: Deploy to Cloud Run
echo -e "${YELLOW}Deploying to Cloud Run...${NC}"

# Build the base command
DEPLOY_CMD="gcloud run deploy ${SERVICE_NAME} \
  --image ${IMAGE_NAME} \
  --platform managed \
  --region ${REGION} \
  --port 4000 \
  --memory 2Gi \
  --cpu 2 \
  --timeout 600 \
  --set-env-vars LITELLM_MASTER_KEY=${LITELLM_MASTER_KEY},VERTEX_PROJECT=${PROJECT_ID},VERTEX_LOCATION=${REGION}"

# Add DATABASE_URL if set
if [ ! -z "$DATABASE_URL" ]; then
    DEPLOY_CMD="${DEPLOY_CMD},DATABASE_URL=${DATABASE_URL}"
fi

# Add Cloud SQL connection if present
if [ ! -z "$CLOUD_SQL_CONNECTION" ]; then
    DEPLOY_CMD="${DEPLOY_CMD} --add-cloudsql-instances ${CLOUD_SQL_CONNECTION}"
fi

# Add service account if exists
if gcloud iam service-accounts describe ${SERVICE_NAME}@${PROJECT_ID}.iam.gserviceaccount.com &>/dev/null; then
    DEPLOY_CMD="${DEPLOY_CMD} --service-account ${SERVICE_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
fi

# Execute deployment
eval $DEPLOY_CMD

echo -e "${GREEN}Deployment complete!${NC}"
echo ""
echo "Service URL:"
gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format 'value(status.url)'
echo ""
echo -e "${YELLOW}Access the dashboard at: <SERVICE_URL>/ui${NC}"
echo -e "${YELLOW}API endpoint: <SERVICE_URL>/chat/completions${NC}"
