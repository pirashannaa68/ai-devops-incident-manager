---
title: AI DevOps Incident Manager
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

# DevOps Incident Management Environment

An [OpenEnv](https://github.com/meta-pytorch/OpenEnv) environment that simulates distributed system incident response. Each episode presents a production failure scenario; the agent must diagnose the root cause and apply the correct remediation using a discrete set of SRE commands.

## Quick Start

```python
from my_env import DevOpsAction, DevOpsEnv

try:
    env = DevOpsEnv.from_docker_image("openenv/my_env_env:latest")

    obs = env.reset(task_name="easy")
    print(obs.observation.active_alerts)
    # ["CRITICAL: High CPU on auth-api (99%)"]

    result = env.step(DevOpsAction(command="get_logs", target="auth-api"))
    print(result.observation.action_feedback)
    # "[ERROR] Request queue full, dropping connects."

    result = env.step(DevOpsAction(command="restart_service", target="auth-api"))
    print(result.reward)   # 0.9 (resolved in 2 steps)
    print(result.done)     # True

finally:
    env.close()
```

## Environment Design

### Observation Space

Each step returns a `DevOpsObservation` with:

| Field | Type | Description |
|---|---|---|
| `task_description` | `str` | Active incident pager message |
| `active_alerts` | `List[str]` | Priority-tagged system alerts |
| `services` | `List[ServiceStatus]` | Real-time telemetry for all 8 services |
| `action_feedback` | `str` | Output from the last command |
| `total_cost` | `float` | Cumulative infrastructure burn-rate |
| `total_downtime` | `float` | Cumulative SLA penalty |
| `done` | `bool` | Episode completion flag |
| `reward` | `float` | Step reward signal |

`ServiceStatus` fields: `name`, `status`, `severity`, `cpu_usage`, `memory_usage`, `latency_ms`, `error_rate`, `cost_per_minute`.

### Action Space

Agents issue commands via `DevOpsAction(command, target, args?)`:

| Command | Target | Effect |
|---|---|---|
| `get_logs` | service name | Returns filtered log output. Optional `args` for grep. |
| `restart_service` | service name | Clears transient state. Incurs downtime penalty. |
| `rollback_deployment` | service name | Reverts a faulty deployment. Resolves config errors. |
| `add_db_index` | table name | Queues a deferred index creation (takes 2 steps). |
| `scale_service` | service name | Reduces CPU load. Triples cost-per-minute. |
| `wait` | `none` | Observes for one step without acting. |
| `finish` | — | Terminates the episode. |

### Reward Function

- `+0.05` — diagnostic action (`get_logs`)
- `+0.10` — root-cause identification bonus (hard task only)
- `+0.20–0.50` — correct remediation applied
- `-0.10` — wrong target, repeated action, or blind index
- **Terminal**: `grade()` replaces the final step reward, exposing the normalized score to the evaluator.

`grade()` returns `0.01` for unresolved episodes and `0.30–0.99` for resolved episodes based on step efficiency.

## Tasks

Three scenarios of increasing complexity:

### Easy
- **Scenario**: High CPU on `auth-api` causing elevated API latency.
- **Root cause**: Thread pool exhaustion; clearable with `restart_service`.
- **Optimal solution**: `get_logs auth-api` → `restart_service auth-api` (2 steps).
- **Max score**: `0.90`

### Medium
- **Scenario**: Concurrent incidents — faulty deployment on `payment-gateway` and disk OOM on `search-index`.
- **Root cause**: Missing config key introduced in `v2.1` deployment.
- **Optimal solution**: `get_logs payment-gateway` → `rollback_deployment payment-gateway` → `restart_service search-index` (3 steps).
- **Max score**: `0.85`

### Hard
- **Scenario**: Cascading DB latency causing `web-frontend` 504s and Redis OOM.
- **Root cause**: Missing index on `transactions.user_id` causing full table scans.
- **Optimal solution**: `get_logs database` → `restart_service redis-cache` → `add_db_index transactions` → `wait` → `wait` (5 steps, async).
- **Max score**: `0.76`

A stochastic chaos engine (p=0.15 per step) injects secondary faults on healthy services to prevent pattern memorization.

## Baseline Scores

Scores are produced by `env.grade()` in range `(0.01, 0.99)`:

| Agent | Easy | Medium | Hard |
|---|---|---|---|
| Random | 0.01 | 0.01 | 0.01 |
| Rule-based | 0.60–0.85 | 0.35–0.60 | 0.05–0.15 |
| LLM (GPT-4o) | 0.85–0.99 | 0.50–0.75 | 0.30–0.60 |

Scores decay based on step efficiency: resolving at step 1 yields `0.99`, at step 15 yields `0.30`.

## Project Structure

```
my_env/
├── __init__.py                  # Public module exports
├── openenv.yaml                 # OpenEnv manifest
├── pyproject.toml               # Project metadata and dependencies
├── Dockerfile                   # Container image definition
├── README.md                    # This file
├── models.py                    # Action and Observation Pydantic schemas
├── client.py                    # DevOpsEnv HTTP/WebSocket client
├── inference.py                 # Evaluation runner (random, rule-based, LLM agents)
└── server/
    ├── my_env_environment.py    # Core MDP — state transitions and reward logic
    └── app.py                   # FastAPI application (HTTP + WebSocket endpoints)
```

## Setup

### Local Development

```bash
# Install dependencies
uv sync
# or
pip install -e .

# Start the server
uvicorn server.app:app --host 0.0.0.0 --port 8000

# In a separate terminal, run the inference benchmark
HF_TOKEN=<your_token> python inference.py
```

### Docker

```bash
docker build -t openenv/my_env_env:latest .
docker run -p 8000:8000 openenv/my_env_env:latest
```

### OpenEnv Validation

```bash
openenv validate
```

### Inference Benchmark

The inference script runs all 3 tasks against 3 agent types and emits structured logs:

```
[START] task=easy env=DevOps model=random
[STEP] step=1 action={"command":"get_logs","target":"auth-api"} reward=0.05 done=false error=null
[STEP] step=2 action={"command":"restart_service","target":"auth-api"} reward=0.90 done=true error=null
[END] success=true steps=2 rewards=0.05,0.90
```

Environment variables:

| Variable | Default | Required |
|---|---|---|
| `API_BASE_URL` | `https://api.openai.com/v1` | No |
| `MODEL_NAME` | `gpt-4o` | No |
| `HF_TOKEN` | — | **Yes** |

## Deployment

Live at: `https://huggingface.co/spaces/Pirashannaa68/ai-devops-incident-manager`

Endpoints:
- `POST /reset` — Initialize episode with `{"task_name": "easy|medium|hard"}`
- `POST /step` — Execute `DevOpsAction`
- `GET /state` — Current episode state
- `GET /docs` — Interactive API documentation
- `GET /health` — Container health check

## Use Cases

- **Agent Evaluation**: Benchmark LLM diagnostic and remediation reasoning
- **RL Training**: Dense reward signal across multi-step SRE workflows
- **Curriculum Learning**: Progressive difficulty from single-service to cascading failures
- **Research**: Causal reasoning under uncertainty in real-world production topologies

## Learn More

- [OpenEnv Documentation](https://github.com/meta-pytorch/OpenEnv)
- [OpenEnv Environment Design Guide](https://github.com/meta-pytorch/OpenEnv/blob/main/README.md)
