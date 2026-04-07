# DevOps Incident Manager Environment

An OpenEnv reinforcement learning environment that simulates distributed system incident response. The agent acts as an on-call Site Reliability Engineer (SRE), diagnosing and resolving failures across an 8-service microservice topology.

---

## Problem the Environment Solves

The environment provides a platform to train and evaluate reinforcement learning agents in diagnosing and remediating complex distributed systems problems under uncertainty. It models realistic conditions including multi-incident scenarios, stochastic failure injection, causal service dependencies, and infrastructure cost tracking. 

The agent observes real-time service telemetry—such as CPU usage, memory, latency, and error rates—and must efficiently select remediation actions to restore the system to a healthy state while minimizing downtime and infrastructure costs.

---

## System Architecture

The environment is built using the OpenEnv framework and utilizes a standard client-server architecture:

- **`server/app.py`**: A FastAPI server that exposes the environment over HTTP/WebSocket, providing the standard `step`, `reset`, and `state` endpoints.
- **`server/my_env_environment.py`**: The core environment logic. It manages the Markov state transitions, the reward function, and the final episode grader.
- **`models.py`**: Defines strictly-typed Pydantic schemas for the environment's observation and action space.
- **`inference.py`**: The baseline inference script that exposes Random, Rule-Based, and Language Model agents to the environment.

---

## RL Environment Design (State, Action, Reward)

The environment models a Markov Decision Process (MDP) with a horizon of 15 steps and a discount factor ($\gamma$) of 0.99.

### State Space

The observation space consists of per-service performance vectors across 8 services, aggregated alongside episode-specific metadata.

**Service Metrics:**
- `status` (running, degraded, down)
- `severity` (low, medium, critical)
- `cpu_usage`, `memory_usage` (%)
- `latency_ms`
- `error_rate` (%)
- `cost_per_minute`

**Episode Metadata:**
- `task_description`
- `active_alerts`
- `action_feedback` (from the prior step)
- `total_cost` & `total_downtime`

### Action Space

The action space is a discrete vocabulary targeted at specific components in the topology. 

```python
command: Literal[
    "get_logs",            # Retrieve service logs; accepts optional grep filter
    "restart_service",     # Restart a named service; triggers downtime penalty
    "rollback_deployment", # Revert the last deployment on a service
    "add_db_index",        # Queue a database index creation; applies after 2 steps
    "scale_service",       # Increase replicas; reduces CPU load, triples cost_per_minute
    "wait",                # Take no action; advance one step
    "finish"               # Declare incident resolved and terminate episode
]
target: str   # Service name (e.g., "auth-api", "database") or table name
args: str     # Optional. Grep keyword for get_logs (e.g., "ERROR", "WARN")
```

### Reward Function

Rewards are dense and shaped to encourage rapid root-cause isolation and penalize inefficient or destructive operations.

| Event | Reward |
|-------|--------|
| Investigate the correct root-cause service | +0.05 to +0.30 |
| Successful resolution action | +0.50 |
| Horizontal scale (partial mitigation) | +0.10 |
| Blind action without prior investigation | −0.10 |
| Database thundering herd restart | −0.30 |
| Repeated identical action | −0.10 |
| Episode timeout without resolution | −0.50 |

At termination, the terminal step reward is replaced by a normalized final grade:
`max(0, success − steps×0.03 − cost×0.01 − downtime×0.02)`

---

## Expected Outputs

### Baseline Inference Scores

Baseline scores are deterministic when tested using the rule-based agent and LLMs defined in `inference.py`. The normalized grade penalizes elapsed steps, infrastructure cost, and accumulated downtime.

| Agent | Easy | Medium | Hard |
|-------|------|--------|------|
| Random | ~0.05 | ~0.02 | ~0.00 |
| Rule-Based | ~0.40 | ~0.25 | ~0.15 |
| LLM (GPT-4o) | ~0.72 | ~0.58 | ~0.42 |

### Standard Output Log Format

```text
[START] task=<name> env=DevOps model=<agent>
[STEP] step=<n> action=<json> reward=<float> done=<bool>
...
[END] success=<bool> steps=<n> score=<float> rewards=[<list>]
[DEBUG] infra_cost=<float> downtime_penalty=<float>
```

---

## Evaluation Criteria

The RL environment is designed to pass the following quality metrics during evaluation:

1. **Non-trivial exploration:** The performance gap between a Random agent (~0.05), a Rule-Based agent (~0.40), and a frontier LLM (~0.72) demonstrates that the environment rewards genuine reasoning and planning, not just random clicking.
2. **Dense reward signal:** Positive rewards are issued for partial progress (e.g., filtering relevant logs), guiding policy convergence prior to episode resolution.
3. **Reproducibility:** Seeded deterministic components control the primary incident generation, ensuring reproducible scoring. Unseeded stochastic events (chaos injection) test the agent's generalization capabilities during the episode.
4. **Normalized Grade Range:** `[0.0, 1.0]` across all tasks.
5. **Clear Episode Boundaries:** Transitions cleanly enforce `done=True` bounds on resolution, explicit `finish`, or reaching `MAX_STEPS`.
6. **State Fidelity:** The transition dynamics explicitly update the environment's state based on the applied actions and system degradation rules prior to issuing the next observation vector.

---

## Usage

### Local Testing

```bash
cd devops-env/my_env
uv sync
openenv validate

OPENAI_API_KEY=<key> API_BASE_URL=https://api.openai.com/v1 MODEL_NAME=gpt-4o uv run python inference.py
```

### Docker

```bash
docker build -t ai-devops-incident-manager .
docker run -e OPENAI_API_KEY=<key> -e MODEL_NAME=<model> ai-devops-incident-manager
```
