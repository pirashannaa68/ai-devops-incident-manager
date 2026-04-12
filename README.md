---
title: DevOps Incident Manager
emoji: 🛠️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 8000
pinned: false
tags:
  - openenv
  - devops
  - sre
  - evaluation
---

# DevOps Incident Management Environment (DIME)

An [OpenEnv](https://github.com/meta-pytorch/OpenEnv) compliant environment simulating distributed system incident response. The platform exposes an 8-service production topology with realistic telemetry. Each episode presents a progressively complex failure scenario where the system must diagnose the root cause and apply the correct remediation sequence using a discrete action space.

## Quick Start

```python
from my_env import DevOpsAction, DevOpsEnv

try:
    env = DevOpsEnv.from_docker_image("openenv/my_env_env:latest")

    obs = env.reset(task_name="easy")
    print(obs.observation.active_alerts)

    result = env.step(DevOpsAction(command="get_logs", target="auth-api"))
    print(result.observation.action_feedback)

    result = env.step(DevOpsAction(command="restart_service", target="auth-api"))
    
    print(result.reward)
    print(result.done)

finally:
    env.close()
```

## Environment Design

### Observation Space

Each step returns a `DevOpsObservation` containing critical system state:

| Field | Type | Description |
|---|---|---|
| `task_description` | `str` | Active incident pager message |
| `active_alerts` | `List[str]` | Priority-tagged system alerts |
| `services` | `List[ServiceStatus]` | Real-time telemetry for all 8 microservices |
| `action_feedback` | `str` | Output from the preceding diagnostic or remediation command |
| `total_cost` | `float` | Cumulative infrastructure burn-rate |
| `total_downtime` | `float` | Cumulative SLA penalty |
| `done` | `bool` | Episode terminal state flag |
| `reward` | `float` | Intermediate reward signal |

The `ServiceStatus` structure tracks node-level `name`, `status`, `severity`, `cpu_usage`, `memory_usage`, `latency_ms`, `error_rate`, and `cost_per_minute`.

### Action Space

Interaction is facilitated through the `DevOpsAction(command, target, args?)` interface:

| Command | Target | System Effect |
|---|---|---|
| `get_logs` | service name | Retrieves filtered log output for diagnostic analysis. |
| `restart_service` | service name | Cold-starts a service. Incurs a downtime penalty. |
| `rollback_deployment` | service name | Reverts the service artifact, rectifying configuration faults. |
| `add_db_index` | table name | Queues an asynchronous database index execution. |
| `scale_service` | service name | Allocates cluster resources. Triples operational cost. |
| `wait` | `none` | Idles the control cycle for one observation step. |
| `finish` | — | Terminates the current episode loop. |

### Reward Function

The reward function enforces efficient diagnostic workflows:
- `+0.05` — Valid diagnostic execution
- `+0.10` — Root-cause identification marker (hard mode)
- `+0.20–0.50` — Correct remediation deployment
- `-0.10` — Invalid target mapping or redundant command
- **Terminal Boundary**: The `grade()` method evaluates step efficiency against scenario limits, generating a scalar bounding constraint strictly within `(0, 1)`.

## Task Scenarios

The framework includes three escalating deterministic fault topologies. A stochastic failure generator mitigates static pattern memorization by injecting unrelated secondary degradation events.

### Easy
- **Scenario**: Thread pool exhaustion on `auth-api` causing load balancers to timeout.
- **Root cause**: Hanging connection logic.
- **Optimal sequence**: `get_logs auth-api` → `restart_service auth-api`.

### Medium
- **Scenario**: Cascading errors originating from `payment-gateway` conflicting with storage tier alerts.
- **Root cause**: Syntactical failure in the `v2.1` deployment artifact.
- **Optimal sequence**: `get_logs payment-gateway` → `rollback_deployment payment-gateway` → `restart_service search-index`.

### Hard
- **Scenario**: Severe latency on the presentation layer combined with cache node failures.
- **Root cause**: Unindexed relational joins forcing full table scans across the data persistent tier.
- **Optimal sequence**: `get_logs database` → `restart_service redis-cache` → `add_db_index transactions` → `wait` → `wait`.

## Performance Baselines

Average terminal scalars computed through Monte Carlo execution across various operational heuristics:

| Controller | Easy | Medium | Hard |
|---|---|---|---|
| Random Execution | 0.01 | 0.01 | 0.01 |
| Deterministic Ruleset | 0.60–0.85 | 0.35–0.60 | 0.05–0.15 |
| Dynamic Control | 0.85–0.99 | 0.50–0.75 | 0.30–0.60 |

## Setup & Deployment

### Local Initialization

```bash
uv sync

uvicorn server.app:app --host 0.0.0.0 --port 8000

# Execute baseline evaluation framework
HF_TOKEN=<your_token> python inference.py
```

### Containerization

```bash
docker build -t openenv/my_env_env:latest .
docker run -p 8000:8000 openenv/my_env_env:latest
```

## Evaluator Endpoints

The network server provides specification-compliant standard methods:
- `POST /reset` — Bootstraps environment state machine
- `POST /step` — Applies discrete inputs against the MDP
- `GET /state` — Returns raw environment internals
- `GET /health` — Deployment verification

## Documentation References

- [OpenEnv Verification Guide](https://github.com/meta-pytorch/OpenEnv)
