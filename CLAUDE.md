# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository deploys **LiteLLM** as a unified AI model gateway on Google Cloud Platform (GCP) Cloud Run. LiteLLM provides an OpenAI-compatible API that routes requests to VertexAI models (Gemini, Claude) with built-in monitoring, cost tracking, and a dashboard UI.

**Core Architecture**:
- **LiteLLM Proxy**: OpenAI-compatible gateway (port 4000)
- **VertexAI Integration**: Connects to Gemini Flash, Claude Haiku via VertexAI
- **Cloud Run**: Serverless container hosting with auto-scaling
- **Dashboard**: Built-in UI at `/ui` for monitoring usage and costs
- **Prometheus Metrics**: Enabled for monitoring and observability

## Key Configuration Files

- **`litellm_config.yaml`**: LiteLLM configuration (models, callbacks, settings)
  - Model definitions with VertexAI parameters
  - Environment variable interpolation with `os.environ/VAR_NAME`
  - Prometheus callbacks for metrics collection

- **`.env`**: Environment variables (NEVER commit this file)
  - `LITELLM_MASTER_KEY`: API authentication key
  - `VERTEX_PROJECT`: GCP project ID
  - `VERTEX_LOCATION`: GCP region (e.g., us-central1)
  - `DATABASE_URL`: PostgreSQL connection string (optional, SQLite fallback)
  - `UI_USERNAME`/`UI_PASSWORD`: Dashboard credentials

- **`Dockerfile`**: Uses official LiteLLM image (`ghcr.io/berriai/litellm:main-latest`)
  - Exposes port 4000
  - Runs with `--detailed_debug` flag for verbose logging

## Deployment

### Deploy to Cloud Run
```bash
# Load environment variables
source .env

# Run deployment script
./deploy.sh
```

**Deployment Script** (`deploy.sh`):
- Builds container image via Cloud Build
- Deploys to Cloud Run with 2Gi memory, 2 CPU, 600s timeout
- Auto-detects Cloud SQL connection from `DATABASE_URL`
- Auto-attaches service account if it exists

### Manual Deployment
```bash
# Build image
gcloud builds submit --tag gcr.io/${VERTEX_PROJECT}/litellm-gateway .

# Deploy to Cloud Run
gcloud run deploy litellm-gateway \
  --image gcr.io/${VERTEX_PROJECT}/litellm-gateway \
  --platform managed \
  --region ${VERTEX_LOCATION} \
  --port 4000 \
  --memory 2Gi \
  --cpu 2 \
  --timeout 600 \
  --set-env-vars "LITELLM_MASTER_KEY=${LITELLM_MASTER_KEY},VERTEX_PROJECT=${VERTEX_PROJECT},VERTEX_LOCATION=${VERTEX_LOCATION}" \
  --service-account litellm-gateway@${VERTEX_PROJECT}.iam.gserviceaccount.com
```

## Service Account Requirements

The Cloud Run service requires a service account with:
- **`roles/aiplatform.user`**: Access to VertexAI models
- **`roles/storage.objectViewer`**: Access to Cloud Storage (if needed)

Create service account:
```bash
gcloud iam service-accounts create litellm-gateway \
  --display-name "LiteLLM Service Account"

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:litellm-gateway@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"
```

## Testing the Gateway

### Using OpenAI SDK (Python)
```python
from openai import OpenAI

client = OpenAI(
    api_key="sk-your-litellm-master-key",
    base_url="https://your-service-url"
)

response = client.chat.completions.create(
    model="gemini-flash",  # or claude-haiku
    messages=[{"role": "user", "content": "Hello!"}]
)
```

### Using curl
```bash
curl https://your-service-url/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-your-master-key" \
  -d '{"model": "gemini-flash", "messages": [{"role": "user", "content": "Hello!"}]}'
```

### Dashboard Access
- URL: `https://your-service-url/ui`
- Login with `UI_USERNAME` and `UI_PASSWORD` from `.env`

## Google ADK Integration

The `examples/adk_integration.py` demonstrates how to configure Google's Agent Development Kit (ADK) to route requests through the LiteLLM gateway instead of directly calling VertexAI.

**Key Integration Pattern**:
```python
import os
import litellm

# Configure LiteLLM proxy
os.environ["LITELLM_PROXY_API_BASE"] = "https://your-gateway-url"
os.environ["LITELLM_PROXY_API_KEY"] = os.getenv("LITELLM_MASTER_KEY")

# Enable proxy mode
litellm.use_litellm_proxy = True

# Create ADK agent with LiteLlm backend
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

agent = Agent(
    name="agent_name",
    model=LiteLlm(model="gemini-flash", api_key="sk-master-key"),
    instruction="Your agent instructions"
)
```

**Cloud Run Authentication**: If the gateway requires authentication, use identity tokens:
```python
import subprocess

def get_identity_token():
    result = subprocess.run(
        ["gcloud", "auth", "print-identity-token"],
        capture_output=True, text=True, check=True
    )
    return result.stdout.strip()

# Add to agent extra_headers
extra_headers={"Authorization": f"Bearer {get_identity_token()}"}
```

## Available Models

Configured in `litellm_config.yaml`:
- **`gemini-flash`**: Gemini 2.5 Flash (fast, cost-effective)
- **`claude-haiku`**: Claude 3.5 Haiku (via VertexAI Model Garden)

Models use VertexAI backend with format: `vertex_ai/[model-name]@[version]`

## Monitoring and Debugging

### View Logs
```bash
gcloud run logs read litellm-gateway --region ${VERTEX_LOCATION}

# Stream logs
gcloud run logs tail litellm-gateway --region ${VERTEX_LOCATION}
```

### Access Prometheus Metrics
LiteLLM exports metrics to Prometheus endpoints (configured via `success_callback`, `failure_callback`, `service_callback` in config).

### Dashboard Monitoring
The dashboard shows:
- Request volumes and patterns
- Token usage per model
- Cost tracking
- Error rates and status codes
- Model performance metrics

## Database Configuration

**Development**: LiteLLM defaults to SQLite (stored in container, ephemeral)

**Production**: Use Cloud SQL PostgreSQL for persistent usage tracking:
1. Create Cloud SQL instance
2. Set `DATABASE_URL` in `.env`:
   ```
   DATABASE_URL=postgresql://user:password@/dbname?host=/cloudsql/project:region:instance
   ```
3. Add Cloud SQL connection to deployment:
   ```bash
   --add-cloudsql-instances project:region:instance
   ```

## Security Considerations

- **Never commit** `.env` or any files containing secrets
- Master key format: `sk-[secure-random-string]` (generate with `openssl rand -hex 32`)
- Use Secret Manager for production secrets
- Service account follows principle of least privilege
- Dashboard requires username/password authentication
- All API requests require Bearer token authentication

## Common Issues

### Authentication Errors
- Verify service account has `roles/aiplatform.user`
- Ensure `VERTEX_PROJECT` matches your GCP project ID
- Check VertexAI API is enabled: `gcloud services enable aiplatform.googleapis.com`

### Model Not Available
- Verify model is available in your VertexAI region
- For Claude models, enable Anthropic Claude in VertexAI Model Garden
- Check model versions match VertexAI documentation

### Database Connection Issues
- Verify `DATABASE_URL` format matches Cloud SQL requirements
- Check Cloud SQL instance is running and accessible
- Ensure Cloud SQL connection is added to Cloud Run deployment

## Repository Structure

```
.
├── Dockerfile                    # Container definition using LiteLLM base image
├── litellm_config.yaml          # LiteLLM model and settings configuration
├── deploy.sh                    # Automated Cloud Run deployment script
├── .env.example                 # Template for environment variables
├── main.py                      # Simple Python entrypoint (not used by Docker)
├── pyproject.toml              # Python dependencies (google-adk, litellm)
├── examples/
│   ├── adk_integration.py      # Google ADK integration example
│   └── multi_agent_config.yaml # Multi-agent configuration example
└── README.md / SETUP.md        # Documentation
```

## Development Dependencies

Uses `uv` package manager (via `pyproject.toml`):
- `google-adk>=1.18.0`: Google Agent Development Kit
- `google-genai>=1.49.0`: Google GenAI SDK
- `litellm>=1.79.3`: LiteLLM proxy library

Install locally for testing:
```bash
uv sync
source .venv/bin/activate
```
