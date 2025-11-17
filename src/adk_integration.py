"""
This example shows how to configure Google's Agent Development Kit (ADK)
to use your LiteLLM gateway as the LLM backend instead of directly calling VertexAI.

Benefits:
- Unified monitoring across all agents
- Cost tracking per agent
- OpenAI-compatible interface through gateway
- Easy model switching without redeploying agents
- Centralized rate limiting and authentication
"""

import os
import litellm
import subprocess
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm

# Get Google Cloud identity token for authenticating to Cloud Run
def get_identity_token():
    """Get identity token for authenticating to Cloud Run service."""
    try:
        result = subprocess.run(
            ["gcloud", "auth", "print-identity-token"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        print("Warning: Could not get identity token. Make sure you're authenticated with gcloud.")
        return None

# Configuration - Set LiteLLM Proxy environment variables
# This tells ADK to route all LiteLLM requests through your gateway
os.environ["LITELLM_PROXY_API_BASE"] = "https://litellm-gateway-73f6uy24bq-ew.a.run.app"
os.environ["LITELLM_PROXY_API_KEY"] = os.getenv("LITELLM_MASTER_KEY", "sk-master-key-secure")

# Get identity token for Cloud Run authentication
identity_token = get_identity_token()
if identity_token:
    # Set the identity token as an authorization header
    os.environ["LITELLM_PROXY_HEADERS"] = f'{{"Authorization": "Bearer {identity_token}"}}'

# Enable LiteLLM proxy mode - this makes all requests go through your gateway
litellm.use_litellm_proxy = True


# ============================================================================
# Method 2: Create ADK Agent with LiteLLM Backend
# ============================================================================

def create_customer_service_agent():
    """
    Example: Customer Service Agent using ADK with LiteLLM gateway.

    This agent uses gemini-flash through the gateway for fast, cost-effective responses.
    The gateway URL and API key are configured via environment variables above.
    """
    # Get identity token for Cloud Run authentication
    identity_token = get_identity_token()

    # Create agent with custom headers for Cloud Run auth
    agent = Agent(
        name="agents",
        model=LiteLlm(
            model="gemini-flash",
            api_key=os.getenv("LITELLM_MASTER_KEY"),
            extra_headers={"X-Serverless-Authorization": f"Bearer {identity_token}"}
        ),
        instruction="""You are a helpful customer service agent.
        You assist customers with product inquiries, returns, and support requests.
        Be polite, concise, and solution-oriented."""
    )

    return agent



if __name__ == "__main__":
    """
    Before running, set these environment variables:

    export LITELLM_BASE_URL="https://your-gateway-url"
    export LITELLM_API_KEY="sk-your-master-key"

    # Optional: Per-agent keys
    export AGENT_CS_KEY="sk-customer-service-key"
    export AGENT_TS_KEY="sk-technical-support-key"
    export AGENT_SALES_KEY="sk-sales-key"
    """

    import uuid
    
    root_agent = create_customer_service_agent()
    
    import asyncio
    from google.adk.sessions import InMemorySessionService
    from google.adk.runners import Runner
    from google.genai import types

    session_service = InMemorySessionService()
    
    runner = Runner(
        agent=root_agent,
        app_name=root_agent.name,
        session_service=session_service
    )
    
    session_id = str(uuid.uuid4())
    
    user_id = "user_test"


    asyncio.run(session_service.create_session(
            app_name=root_agent.name,
            user_id=user_id,
            session_id=session_id,
        )
    )
    
    content = types.Content(
        role="user",
        parts=[
            types.Part.from_text(text="hello, present yourself"),
        ],
    )
    
    for event in runner.run(
            user_id=user_id, session_id=session_id, new_message=content
        ):
        if event.is_final_response():
            final_response = event.content.parts[0].text
            print("Agent Response: ", final_response)

