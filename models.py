# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.

"""
DevOps Incident Management Environment (DIME) Data Models.

This module defines the strictly-typed schemas for communication between
the environment server and the diagnostic agent. It utilizes Pydantic 
for validation and OpenAPI schema generation.
"""

from typing import Literal, List, Optional
from openenv.core.env_server.types import Action, Observation
from pydantic import BaseModel, Field

class ServiceStatus(BaseModel):
    """
    Status and telemetry metrics for an individual microservice.
    """
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
    Discrete action space for system inspection and remediation.
    
    Attributes:
        command: Literal identifier for the operation to execute.
        target: The resource (service or table) affected by the command.
        args: Optional parameters for command modification (e.g., log filtering).
    """
    command: Literal["get_logs", "restart_service", "rollback_deployment", "add_db_index", "scale_service", "wait", "finish"] = Field(
        ..., description="The command to execute"
    )
    target: str = Field(
        ..., description="The target identifier for the command"
    )
    args: Optional[str] = Field(
        default=None, description="Optional arguments for the command"
    )

class DevOpsObservation(Observation):
    """
    State observation yielded by the environment iteration.
    
    Contains system telemetry, active alerts, and feedback from the previous action
    to inform the agent's next decision.
    """
    task_description: str = Field(default="", description="Description of the active task or incident")
    active_alerts: List[str] = Field(default_factory=list, description="List of active system alerts")
    services: List[ServiceStatus] = Field(default_factory=list, description="Current status of all system services")
    action_feedback: str = Field(default="", description="Log output or status resulting from the last action")
    step_count: int = Field(default=0, description="Current step count in the simulation episode")
    total_cost: float = Field(default=0.0, description="Cumulative infrastructural cost incurred")
    total_downtime: float = Field(default=0.0, description="Cumulative downtime SLA penalty")

