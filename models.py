# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Data models for the DevOps Incident Manager.

Defines the observation and action spaces utilizing strictly-typed Pydantic schemas.
"""

from typing import Literal, List, Optional
from openenv.core.env_server.types import Action, Observation
from pydantic import BaseModel, Field

class ServiceStatus(BaseModel):
    name: str = Field(description="Name of the microservice")
    status: Literal["running", "degraded", "down"] = Field(description="Current status of the service")
    severity: Literal["low", "medium", "critical"] = Field(default="medium", description="Priority level of the service for SLAs")
    cpu_usage: float = Field(description="CPU usage percentage")
    memory_usage: float = Field(description="Memory usage percentage")
    latency_ms: float = Field(description="Average latency in milliseconds")
    error_rate: float = Field(description="Error rate percentage")
    cost_per_minute: float = Field(default=0.0, description="Run-rate infrastructural cost of this node")

class DevOpsAction(Action):
    """
    Defines the discrete action space for environment remediation.
    """
    command: Literal["get_logs", "restart_service", "rollback_deployment", "add_db_index", "scale_service", "wait", "finish"] = Field(
        ..., description="The command to execute (e.g., get logs to investigate, restart a service, scale a service, or finish if resolved)"
    )
    target: str = Field(
        ..., description="The target identifier for the command. This is usually the service name (e.g., 'auth-api', 'payment-gateway', 'database', 'web-frontend') or table name (e.g. 'transactions')."
    )
    args: Optional[str] = Field(
        default=None, description="Optional arguments for the command (e.g., a regex or keyword to grep within logs)."
    )

class DevOpsObservation(Observation):
    """
    Defines the state observation space yielded by the environment.
    """
    task_description: str = Field(default="", description="Description of the active task or incident")
    active_alerts: List[str] = Field(default_factory=list, description="List of active system alerts")
    services: List[ServiceStatus] = Field(default_factory=list, description="Current status of all system services")
    action_feedback: str = Field(default="", description="Feedback or log output resulting from the last action")
    step_count: int = Field(default=0, description="Current step count in the simulation episode")
    total_cost: float = Field(default=0.0, description="Cumulative infrastructural cost incurred.")
    total_downtime: float = Field(default=0.0, description="Cumulative downtime SLA penalty.")
