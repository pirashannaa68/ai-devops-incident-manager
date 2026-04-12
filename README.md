# DevOps Incident Management Environment (DIME)

DIME is an OpenEnv-compliant simulation platform designed to evaluate automated diagnostic and remediation capabilities within a distributed systems context. The environment models an 8-service production topology, streaming realistic telemetry, structured logs, and system alerts. 

The primary objective is to accurately diagnose complex, multi-service cascading failures and apply the optimal sequence of remediation commands within strict operational and temporal constraints.

## Architecture & Integration

DIME exposes a stateful Markov Decision Process (MDP) over standard HTTP and WebSocket interfaces, allowing seamless integration with external control frameworks.

```python
from my_env import DevOpsAction, DevOpsEnv

try:
    env = DevOpsEnv.from_docker_image("openenv/my_env_env:latest")
    
    # Initialize the simulation with a defined failure profile
    obs = env.reset(task_name="easy")
    print(f"Active Alerts: {obs.observation.active_alerts}")
    
    # Execute a diagnostic telemetry retrieval
    result = env.step(DevOpsAction(command="get_logs", target="auth-api"))
    print(f"Diagnostics: {result.observation.action_feedback}")
    
    # Execute remediation payload
    result = env.step(DevOpsAction(command="restart_service", target="auth-api"))
    print(f"Terminal Reward: {result.reward}")

finally:
    env.close()
```

## System Interfaces

### Observation Model

At each simulation step, the environment returns a comprehensive telemetry snapshot:

| Field | Type | Description |
|---|---|---|
| `task_description` | `str` | Active incident pager payload and context. |
| `active_alerts` | `List[str]` | Monitored system alerts prioritized by severity. |
| `services` | `List[ServiceStatus]` | Real-time node-level telemetry (CPU, Memory, Latency, Error Rate). |
| `action_feedback` | `str` | Standard output or error trace from the preceding operation. |
| `total_cost` | `float` | Cumulative infrastructure burn rate. |
| `total_downtime` | `float` | Cumulative downtime SLA penalty index. |
| `done` | `bool` | Evaluation horizon or resolution termination flag. |
| `reward` | `float` | Immediate execution reward scalar. |

### Control Interface (Action Space)

The control system interacts with the environment state exclusively via the `DevOpsAction` schema:

| Command | Target Node/Service | Operational Effect |
|---|---|---|
| `get_logs` | Service ID | Retrieves filtered component logs for diagnostic analysis. |
| `restart_service` | Service ID | Reboots the service. Incurs a downtime SLA penalty. |
| `rollback_deployment` | Service ID | Reverts the deployment artifact to the previous stable state. |
| `add_db_index` | Table Key | Queues an asynchronous database index build. Resolves after a fixed delay. |
| `scale_service` | Service ID | Horizontally scales resources. Significantly increases infrastructure cost. |
| `wait` | None | Yields the execution context for one cycle. |
| `finish` | None | Terminates the operational envelope and signals task completion. |

## Scoring & Evaluation Metrics

The environment evaluates control policies based on time-to-resolution, diagnostic accuracy, and operational cost management. Suboptimal paths, such as scaling resources instead of resolving underlying faults, receive heavy metric penalization.

* **Diagnostic Operations:** +0.05 modifier for logically sound operational checks.
* **Remediation Execution:** +0.20 to +0.50 modifier for deploying correct fixes.
* **Operational Penalties:** -0.10 modifier for redundant or invalid target mapping.
* **Boundary Confinement:** The final normalized scalar is mathematically clamped within a strict `(0, 1)` range, facilitating straightforward integration with standard evaluation matrices.

## Topologies & Incident Profiles

The environment maintains three deterministic fault scenarios, supplemented by a stochastic perturbation engine to mitigate static sequence memorization.

1. **Profile A (Easy):** Thread pool exhaustion on edge APIs leading to cascading timeouts. Resolution requires isolated restarts.
2. **Profile B (Medium):** Concurrency faults involving invalid deployment artifacts and storage tier degradation. Resolution requires rolling back dependent services and stabilizing data planes.
3. **Profile C (Hard):** Unindexed relational joins forcing distributed table scans, saturating core networking infrastructure, and triggering upstream OOM conditions. Requires coordinated sequential remediation.

## Deployment Guidelines

### Local Development

Dependency synchronization and initialization:

```bash
uv sync
uvicorn server.app:app --host 0.0.0.0 --port 8000
python inference.py
```

### Container Orchestration

The platform is designed to be fully containerized without requiring external data plane dependencies:

```bash
docker build -t openenv/dime_server:latest .
docker run -p 8000:8000 openenv/dime_server:latest
```

## References

For additional documentation regarding the underlying MDP communication protocol, refer to the [OpenEnv Specifications](https://github.com/meta-pytorch/OpenEnv).
