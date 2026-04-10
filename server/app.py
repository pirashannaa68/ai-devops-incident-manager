# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.

"""
FastAPI application for the DevOps Incident Management Environment.

This module creates an HTTP server that exposes MyEnvironment
over HTTP and WebSocket endpoints, compatible with EnvClient.

Endpoints:
    - POST /reset: Reset the environment
    - POST /step: Execute an action
    - GET /state: Get current environment state
    - GET /schema: Get action/observation schemas
    - WS /ws: WebSocket endpoint for persistent sessions

Usage:
    uvicorn server.app:app --reload --host 0.0.0.0 --port 8000
    uvicorn server.app:app --host 0.0.0.0 --port 8000 --workers 4
    python -m server.app
"""

import os
import sys

# Add project root to sys.path for robust module discovery in all environments
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# API Configuration
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

# Import models with try/except fallback for in-repo vs standalone
try:
    from models import DevOpsAction, DevOpsObservation  # type: ignore
except ImportError:
    from ..models import DevOpsAction, DevOpsObservation  # type: ignore

from server.my_env_environment import MyEnvironment  # type: ignore


# Create the OpenEnv-compliant FastAPI application
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
    """Redirects root to the interactive API documentation."""
    return RedirectResponse(url="/docs")


def main(host: str = "0.0.0.0", port: int = 8000):
    """
    Entry point for direct server execution.

    Args:
        host: Interface address (use '0.0.0.0' for Docker/HuggingFace).
        port: Network port for incoming connections.
    """
    import uvicorn

    print("\n" + "="*60)
    print(" [SYSTEM] DevOps Incident Management Environment Initializing...")
    print(f" [URL]    Access Interface: http://{host}:{port}")
    print("=" * 60 + "\n")

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()
    main(host=args.host, port=args.port)


