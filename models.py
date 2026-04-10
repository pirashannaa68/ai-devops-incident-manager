# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.

"""
DevOps Incident Management Environment — Data Models.

Defines the typed schemas for the action and observation spaces.
Pydantic models are used for runtime validation and OpenAPI schema generation.
"""

from typing import Literal, List, Optional
from openenv.core.env_server.types import Action, Observation
from pydantic import BaseModel, Field


class ServiceStatus(BaseModel):
    """Real-time telemetry for a single microservice node."""

    name: str = Field(description="Service identifier")
    status: Literal["running", "degraded", "down"] = Field(description="Operational state")
    severity: Literal["low", "medium", "critical"] = Field(
        default="medium", description="SLA priority tier"
    )
    cpu_usage: float = Field(description="CPU utilization (%)")
    memory_usage: float = Field(description="Memory utilization (%)")
    latency_ms: float = Field(description="P99 request latency (ms)")
    error_rate: float = Field(description="Error rate (%)")
    cost_per_minute: float = Field(default=0.0, description="Infrastructure run-rate cost")


class DevOpsAction(Action):
    """
    Discrete action issued by the agent to inspect or remediate infrastructure.

    Attributes:
        command: The operation to execute.
        target: Service name or resource identifier the command applies to.
        args: Optional filter string (used with ``get_logs`` for grep-style filtering).
    """

    command: Literal[
        "get_logs", "restart_service", "rollback_deployment",
        "add_db_index", "scale_service", "wait", "finish",
    ] = Field(..., description="Operation to execute")
    target: str = Field(..., description="Target service or resource")
    args: Optional[str] = Field(default=None, description="Optional command arguments")


class DevOpsObservation(Observation):
    """
    System state snapshot returned after each environment step.

    Contains service telemetry, active alerts, and feedback from the previous
    action to inform the agent's next decision. The ``done`` and ``reward``
    fields are declared explicitly to satisfy the OpenEnv framework schema
    validator, which reads them via introspection before running episodes.
    """

    done: bool = Field(False, description="Episode completion flag")
    reward: Optional[float] = Field(None, description="Step reward")
    task_description: str = Field(default="", description="Active incident pager message")
    active_alerts: List[str] = Field(default_factory=list, description="Priority-tagged system alerts")
    services: List[ServiceStatus] = Field(default_factory=list, description="Telemetry for all monitored services")
    action_feedback: str = Field(default="", description="Log output or status from the last command")
    step_count: int = Field(default=0, description="Current step within the episode")
    total_cost: float = Field(default=0.0, description="Cumulative infrastructure cost incurred")
    total_downtime: float = Field(default=0.0, description="Cumulative SLA downtime penalty")
    metadata: Optional[dict] = Field(default=None, description="Auxiliary episode metadata")
