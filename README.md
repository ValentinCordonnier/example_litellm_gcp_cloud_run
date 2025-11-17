# LiteLLM Gateway on Google Cloud Run

Deploy LiteLLM as a unified AI model gateway on Google Cloud Platform with VertexAI integration. This setup provides an OpenAI-compatible API for Gemini and Claude models, with built-in monitoring, cost tracking, and authentication.

## What is this?

This repository provides a production-ready setup for deploying [LiteLLM](https://github.com/BerriAI/litellm) on GCP Cloud Run. The gateway:

- Provides an OpenAI-compatible API for VertexAI models (Gemini Flash, Claude Haiku)
- Includes a built-in dashboard for monitoring usage and costs
- Handles authentication via master key
- Scales automatically with Cloud Run
- Exports Prometheus metrics for observability

## Prerequisites

Before deploying, you need:

1. **Google Cloud Project** with billing enabled
2. **gcloud CLI** installed and authenticated
3. **Required permissions** to:
   - Deploy to Cloud Run
   - Create service accounts
   - Enable APIs
   - Use VertexAI

## Step 1: Configure Environment Variables

1. Copy the environment template:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your values:
   ```bash
   # Generate a secure master key
   LITELLM_MASTER_KEY=$(openssl rand -hex 32)

   # Your GCP project details
   VERTEX_PROJECT=your-gcp-project-id
   VERTEX_LOCATION=us-central1

   # Optional: Database for persistent storage
   DATABASE_URL=postgresql://user:pass@/db?host=/cloudsql/project:region:instance
   ```

   **Important**: Never commit the `.env` file to git!

## Step 2: Enable Required APIs

```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  aiplatform.googleapis.com \
  compute.googleapis.com
```

## Step 3: Create Service Account

The Cloud Run service needs a service account with VertexAI permissions:

```bash
export PROJECT_ID="your-gcp-project-id"
export SERVICE_NAME="litellm-gateway"

# Create service account
gcloud iam service-accounts create ${SERVICE_NAME} \
  --display-name "LiteLLM Service Account"

# Grant VertexAI User role
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SERVICE_NAME}@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"
```

## Step 4: Deploy to Cloud Run

### Option A: Automated Deployment (Recommended)

```bash
# Load environment variables
source .env

# Make the script executable
chmod +x deploy.sh

# Run deployment
./deploy.sh
```

The script will:
- Build the Docker container using Cloud Build
- Deploy to Cloud Run with optimal settings (2GB memory, 2 CPUs, 600s timeout)
- Configure environment variables
- Attach the service account
- Output the service URL

### Option B: Manual Deployment

```bash
# Set your project
gcloud config set project ${VERTEX_PROJECT}

# Build the container image
gcloud builds submit --tag gcr.io/${VERTEX_PROJECT}/litellm-gateway .

# Deploy to Cloud Run
gcloud run deploy litellm-gateway \
  --image gcr.io/${VERTEX_PROJECT}/litellm-gateway \
  --platform managed \
  --region ${VERTEX_LOCATION} \
  --allow-unauthenticated \
  --port 4000 \
  --memory 2Gi \
  --cpu 2 \
  --timeout 600 \
  --set-env-vars "LITELLM_MASTER_KEY=${LITELLM_MASTER_KEY},VERTEX_PROJECT=${VERTEX_PROJECT},VERTEX_LOCATION=${VERTEX_LOCATION}" \
  --service-account ${SERVICE_NAME}@${VERTEX_PROJECT}.iam.gserviceaccount.com
```

## Step 5: Test Your Gateway

After deployment, you'll get a service URL like: `https://litellm-gateway-xxx-uc.a.run.app`

### Test with curl

```bash
export GATEWAY_URL="https://your-service-url"
export MASTER_KEY="your-litellm-master-key"

curl ${GATEWAY_URL}/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${MASTER_KEY}" \
  -d '{
    "model": "gemini-flash",
    "messages": [
      {"role": "user", "content": "Hello! How are you?"}
    ]
  }'
```

### Access the Dashboard

1. Navigate to: `https://your-service-url/ui`
2. Login with credentials from your `.env` file (UI_USERNAME/UI_PASSWORD if configured)

The dashboard shows:
- Request volumes and patterns
- Token usage per model
- Cost tracking
- Error rates
- Model performance

## Using with Google ADK (Agent Development Kit)

The `examples/adk_integration.py` file demonstrates how to configure Google's Agent Development Kit to route requests through your LiteLLM gateway.

### Setup

1. **Install dependencies**:
   ```bash
   uv sync
   source .venv/bin/activate
   ```

2. **Set environment variables**:
   ```bash
   export LITELLM_MASTER_KEY="your-master-key-from-env"
   ```

3. **Update the gateway URL** in `examples/adk_integration.py`:
   ```python
   os.environ["LITELLM_PROXY_API_BASE"] = "https://your-service-url"
   ```

### How it Works

The integration uses two authentication mechanisms:

1. **LiteLLM Master Key**: Passed via `api_key` parameter for gateway authentication
2. **IAM Identity Token**: Passed via `X-Serverless-Authorization` header for Cloud Run authentication

```python
import os
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

# Get identity token for Cloud Run
identity_token = get_identity_token()

# Create agent with LiteLLM backend
agent = Agent(
    name="my_agent",
    model=LiteLlm(
        model="gemini-flash",
        api_key=os.getenv("LITELLM_MASTER_KEY"),
        extra_headers={"X-Serverless-Authorization": f"Bearer {identity_token}"}
    ),
    instruction="Your agent instructions here"
)
```

### Run the Example

```bash
python examples/adk_integration.py
```

This will:
1. Get your Google Cloud identity token
2. Create a customer service agent
3. Initialize a session with the agent
4. Send a test message ("hello, present yourself")
5. Print the agent's response

### Key Benefits

- **Unified Monitoring**: All agent requests go through your gateway dashboard
- **Cost Tracking**: Track per-agent costs in one place
- **Easy Model Switching**: Change models without redeploying agents
- **Centralized Auth**: Manage API keys in the gateway, not in agent code

## Available Models

Configured in `litellm_config.yaml`:

- **`gemini-flash`**: Gemini 2.5 Flash (fast, cost-effective)
- **`claude-haiku`**: Claude 3.5 Haiku (via VertexAI Model Garden)

To add more models, edit `litellm_config.yaml` and redeploy.

## Configuration

### Model Configuration (`litellm_config.yaml`)

```yaml
model_list:
  - model_name: gemini-flash
    litellm_params:
      model: vertex_ai/gemini-2.5-flash
      vertex_project: os.environ/VERTEX_PROJECT
      vertex_location: os.environ/VERTEX_LOCATION
```

### Prometheus Metrics

Metrics are automatically exported and can be scraped from `/metrics` endpoint:
- Request counts
- Token usage
- Latency
- Error rates

## Monitoring and Debugging

### View Logs

```bash
# Stream logs
gcloud run logs tail litellm-gateway --region ${VERTEX_LOCATION}

# Read recent logs
gcloud run logs read litellm-gateway --region ${VERTEX_LOCATION} --limit 100
```

### Common Issues

**Authentication Errors:**
- Verify service account has `roles/aiplatform.user`
- Check `VERTEX_PROJECT` matches your GCP project ID
- Ensure VertexAI API is enabled

**Model Not Available:**
- Verify model is available in your VertexAI region
- For Claude models, enable Anthropic Claude in VertexAI Model Garden
- Check model names match VertexAI documentation

**Gateway Connection Issues:**
- Check Cloud Run service is running
- Verify `LITELLM_MASTER_KEY` is correct
- For ADK integration, ensure identity token is valid

## Security Best Practices

1. **Never commit secrets**: Keep `.env` out of git
2. **Use Secret Manager**: For production, store secrets in GCP Secret Manager
3. **Rotate keys regularly**: Change `LITELLM_MASTER_KEY` periodically
4. **Restrict Cloud Run access**: Use `--no-allow-unauthenticated` and IAM for production
5. **Monitor usage**: Set up budget alerts in GCP Console

## Architecture

```
┌─────────────────┐
│  ADK Agents     │
│  Python Apps    │
│  OpenAI SDK     │
└────────┬────────┘
         │
         │ HTTPS + Auth Headers
         │
┌────────▼─────────────────────┐
│   Cloud Run (LiteLLM)        │
│  ┌────────────────────────┐  │
│  │  API Gateway           │  │
│  │  - Master Key Auth     │  │
│  │  - Request Routing     │  │
│  │  - Prometheus Metrics  │  │
│  └────────────────────────┘  │
└────────┬─────────────────────┘
         │
         │ Service Account Auth
         │
┌────────▼─────────┐
│    VertexAI      │
│  - Gemini Flash  │
│  - Claude Haiku  │
└──────────────────┘
```

## Cost Optimization

1. **Use Gemini Flash**: 10x cheaper than Gemini Pro for most tasks
2. **Auto-scaling**: Cloud Run scales to zero when idle
3. **Monitor in Dashboard**: Track spending per model
4. **Set Budget Alerts**: Configure in GCP Billing

## Project Structure

```
.
├── Dockerfile                    # LiteLLM container configuration
├── litellm_config.yaml          # Model and callback settings
├── deploy.sh                    # Automated deployment script
├── .env.example                 # Environment variable template
├── examples/
│   └── adk_integration.py       # Google ADK integration example
├── SETUP.md                     # Detailed setup guide
└── README.md                    # This file
```

## Support

- [LiteLLM Documentation](https://docs.litellm.ai)
- [VertexAI Documentation](https://cloud.google.com/vertex-ai/docs)
- [Cloud Run Documentation](https://cloud.google.com/run/docs)
- [Google ADK Documentation](https://cloud.google.com/vertex-ai/docs/agent-development-kit)

## License

MIT License
