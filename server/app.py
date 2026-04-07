# DevOps Incident Management Environment (DIME)
# High-fidelity SRE simulation for Reinforcement Learning research.

"""
FastAPI application for the My Env Environment.

This module creates an HTTP server that exposes the MyEnvironment
over HTTP and WebSocket endpoints, compatible with EnvClient.

Endpoints:
    - POST /reset: Reset the environment
    - POST /step: Execute an action
    - GET /state: Get current environment state
    - GET /schema: Get action/observation schemas
    - WS /ws: WebSocket endpoint for persistent sessions

Usage:
    # Development (with auto-reload):
    uvicorn server.app:app --reload --host 0.0.0.0 --port 8000

    # Production:
    uvicorn server.app:app --host 0.0.0.0 --port 8000 --workers 4

    # Or run directly:
    python -m server.app
"""

import os

# API Configuration and Environment Variables
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o")
HF_TOKEN = os.getenv("HF_TOKEN")

# Authentication Priority: Environment Variable > HuggingFace Token > Local Access
API_KEY = os.getenv("OPENAI_API_KEY") or HF_TOKEN or "local-dev-token"

try:
    from openenv.core.env_server.http_server import create_app
except Exception as e:  # pragma: no cover
    raise ImportError(
        "openenv is required for the web interface. Install dependencies with '\n    uv sync\n'"
    ) from e

import sys

# Add project root to sys.path to allow robust imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from models import DevOpsAction, DevOpsObservation
from server.my_env_environment import MyEnvironment


# Create the app with web interface and README integration
app = create_app(
    MyEnvironment,
    DevOpsAction,
    DevOpsObservation,
    env_name="my_env",
    max_concurrent_envs=1,  # increase this number to allow more concurrent WebSocket sessions
)

from fastapi.responses import RedirectResponse

@app.get("/")
def read_root():
    return RedirectResponse(url="/docs")


def main(host: str = "127.0.0.1", port: int = 8000):
    """
    Entry point for direct execution via uv run or python -m.
    """
    import uvicorn
    
    print("\n" + "-"*60)
    print(" [SYSTEM] DevOps Incident Management Environment Initializing...")
    print(f" [URL]    Access Interface: http://localhost:{port}")
    print("-" * 60 + "\n")

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == '__main__':
    main()
