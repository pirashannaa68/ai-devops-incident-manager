# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""DevOps Incident Manager Environment Client."""

from typing import Dict, Any

from openenv.core import EnvClient
from openenv.core.client_types import StepResult
from openenv.core.env_server.types import State

from .models import DevOpsAction, DevOpsObservation


class DevOpsEnv(
    EnvClient[DevOpsAction, DevOpsObservation, State]
):
    """
    Client for the DevOps Incident Manager Environment.

    Maintains a persistent connection to the environment server for 
    multi-step SRE incident management simulations.
    """

    def _step_payload(self, action: DevOpsAction) -> Dict:
        """
        Convert DevOpsAction to JSON payload for the server step endpoint.
        """
        return action.model_dump()

    def _parse_result(self, payload: Dict) -> StepResult[DevOpsObservation]:
        """
        Parse server response into StepResult[DevOpsObservation].
        """
        observation_dict = payload.get("observation", {})
        
        # Pydantic will reconstruct the nested models correctly
        observation = DevOpsObservation(**observation_dict)

        return StepResult(
            observation=observation,
            reward=payload.get("reward"),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict) -> State:
        """
        Parse server response into standard State object.
        """
        return State(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
        )
