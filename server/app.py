# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.

"""
FastAPI server for the DevOps Incident Management Environment.

Exposes MyEnvironment over HTTP and WebSocket endpoints using the
OpenEnv create_app factory. All session management, schema generation,
and concurrent-client handling is delegated to the framework.

Endpoints:
    POST /reset  — Initialize or restart an episode.
    POST /step   — Execute a DevOpsAction and receive an observation.
    GET  /state  — Inspect the current episode state.
    GET  /schema — Action and observation JSON schemas.
    GET  /health — Liveness probe for container orchestration.
    WS   /ws     — WebSocket endpoint for low-latency persistent sessions.

Usage:
    uvicorn server.app:app --host 0.0.0.0 --port 8000
    python -m server.app --host 0.0.0.0 --port 8000
"""

import os
import sys

# Ensure the project root is importable regardless of working directory.
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from openenv.core.env_server.http_server import create_app
except Exception as e:  # pragma: no cover
    raise ImportError(
        "openenv-core is required. Install dependencies with:\n    uv sync"
    ) from e

try:
    from models import DevOpsAction, DevOpsObservation  # type: ignore
except ImportError:
    from ..models import DevOpsAction, DevOpsObservation  # type: ignore

try:
    from server.my_env_environment import MyEnvironment  # type: ignore
except ImportError:
    from my_env_environment import MyEnvironment  # type: ignore


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
    """Redirects to the interactive API documentation."""
    return RedirectResponse(url="/docs")


def main(host: str = "0.0.0.0", port: int = 8000) -> None:
    """
    Starts the uvicorn server.

    Args:
        host: Bind address. Use ``0.0.0.0`` for Docker and Hugging Face Spaces.
        port: Listening port.
    """
    import uvicorn

    print("\n" + "="*60)
    print(" DevOps Incident Management Environment")
    print(f" Server: http://{host}:{port}")
    print(f" Docs:   http://{host}:{port}/docs")
    print("=" * 60 + "\n")

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="DevOps Incident Management Environment Server")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()
    main(host=args.host, port=args.port)
