# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.

"""
FastAPI Server for the DevOps Incident Management Environment (DIME).

This module initializes the OpenEnv-compliant HTTP server, surfacing the 
MyEnvironment state machine via REST and WebSocket endpoints for agentic 
interaction.
"""

import os
import sys

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
        "openenv-core is required for the server interface. Install dependencies via `uv sync`."
    ) from e

# Add project root to sys.path to allow robust discovery of local modules
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from models import DevOpsAction, DevOpsObservation  # type: ignore
from server.my_env_environment import MyEnvironment  # type: ignore

# Initialize the OpenEnv structured application
app = create_app(
    MyEnvironment,
    DevOpsAction,
    DevOpsObservation,
    env_name="my_env",
    max_concurrent_envs=1,
)

from fastapi.responses import RedirectResponse

@app.get("/")
def read_root():
    """
    Redirects the root index to the automated API documentation.
    """
    return RedirectResponse(url="/docs")

def main(host: str = "127.0.0.1", port: int = 8000):
    """
    Entry point for direct server execution.
    
    Args:
        host: Interface to bind the server to (e.g., '0.0.0.0' for Docker).
        port: Network port for incoming connections.
    """
    import uvicorn
    
    print("\n" + "="*60)
    print(" [SYSTEM] DevOps Incident Management Environment Initializing...")
    print(f" [URL]    Access Interface: http://{host}:{port}")
    print("=" * 60 + "\n")

    uvicorn.run(app, host=host, port=port, log_level="info")

if __name__ == '__main__':
    main()

