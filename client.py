# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.

"""
Environment Client for the DevOps Incident Management Environment (DIME).

Provides the high-level API wrapper for interacting with the DevOps server 
via standardized REST and WebSocket endpoints.
"""

from typing import Dict, Any
from openenv.core import EnvClient
from openenv.core.client_types import StepResult
from openenv.core.env_server.types import State

from .models import DevOpsAction, DevOpsObservation

class DevOpsEnv(
    EnvClient[DevOpsAction, DevOpsObservation, State]
):
    """
    Client implementation for stable communication with the DevOps Environment.

    Maintains session state and provides strictly-typed serialization 
    for action/observation exchange during incident simulation.
    """

    def _step_payload(self, action: DevOpsAction) -> Dict:
        """
        Converts a DevOpsAction object into a JSON-serializable dictionary.
        
        Args:
            action: The structured remediation command.
            
        Returns:
            A dictionary representation of the action payload.
        """
        return action.model_dump()

    def _parse_result(self, payload: Dict) -> StepResult[DevOpsObservation]:
        """
        Deserializes the server response into a structured StepResult.
        
        Args:
            payload: The dictionary response from the /step endpoint.
            
        Returns:
            A StepResult containing the validated DevOpsObservation and step signal.
        """
        observation_dict = payload.get("observation", {})
        
        # Pydantic reconstructs the nested models and nested service telemetry
        observation = DevOpsObservation(**observation_dict)

        return StepResult(
            observation=observation,
            reward=payload.get("reward"),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict) -> State:
        """
        Extracts high-level environment state from a dictionary payload.
        
        Args:
            payload: The server response containing state information.
            
        Returns:
            A core State object with episode tracking and step count.
        """
        return State(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
        )

