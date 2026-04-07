---
title: AI DevOps Incident Manager
emoji: 📉
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 8000
---
# DevOps Incident Management Environment (DIME)

A high-fidelity reinforcement learning environment for evaluating decision-making agents in complex, distributed system incident response. The environment simulates an 8-service microservice topology where an agent must diagnose, mitigate, and resolve production incidents under stochastic chaos and infrastructural cost constraints.

---

## 1. Problem the Environment Solves

In modern Site Reliability Engineering (SRE), incident response is characterized by **Partial Observability** and **Temporal Dependencies**. Engineers must navigate a "sea of noise" - telemetry, logs, and alerts - to identify the underlying root cause while minimizing Time To Recovery (TTR) and Service Level Agreement (SLA) breaches.

DIME formalizes this challenge as a Markov Decision Process (MDP), providing a standardized platform to train and benchmark agents on:
- **Causal Reasoning:** Distinguishing between symptom services (e.g., a frontend timeout) and root-cause services (e.g., a database locking issue).
- **Cost-Benefit Optimization:** Balancing expensive mitigation strategies (e.g., service scaling) against cheaper investigative actions (e.g., log filtering).
- **Stochastic Failure Resolution:** Managing incidents that evolve dynamically based on previous actions and environmental chaos.

---

## 2. System Architecture

The environment adopts a distributed microservice topology consisting of 8 distinct components:

- **Edge Layer:** `web-frontend` (Entry point for user traffic).
- **Business Logic Layer:** `auth-api`, `payment-gateway`, `user-profile-api`.
- **Worker Layer:** `notification-worker`, `search-index`.
- **Persistence Layer:** `database` (PostgreSQL simulation), `redis-cache`.

### Core Components
- **Simulation Engine:** Implements the state transition logic, casualty propagation, and chaos injection (15% stochastic failure rate).
- **Observability Interface:** Provides real-time metrics (CPU, Memory, Latency, Error Rate) and log access.
- **Remediation API:** Standardized interface for executing system-level actions.

---

## 3. RL Environment Design (State, Action, Reward)

### State Space (S)
The state S is represented as a structured observation vector containing:
- **Service Telemetry:** Real-time performance metrics for all 8 nodes.
- **Alert Buffer:** A FIFO queue of critical system alerts.
- **Action Context:** Feedback from the agent's prior interaction.
- **Global Accounting:** Cumulative infrastructural cost and downtime duration.

### Action Space (A)
The action space A is discrete and targeted, allowing for both investigation and remediation:
- `get_logs(target, filter)`: Retrieve filtered telemetry logs (Low cost, high information gain).
- `restart_service(target)`: Hard reboot of a node (High TTR penalty).
- `scale_service(target)`: Horizontal scaling (High run-rate cost, removes CPU bottlenecks).
- `rollback_deployment(target)`: Reverts deployments (Resolves configuration-based failures).
- `add_db_index(target)`: Database optimization (Delayed effect, permanent latency reduction).

### Reward Function (R)
The reward function is dense and shaped to optimize for efficient resolution:
- **Exploration Signal (+0.05 to +0.30):** Issued upon investigating the correct root-cause service.
- **Resolution Reward (+0.50):** Issued upon successful mitigation of the primary incident.
- **Efficiency Penalties (-0.10):** Applied for blind actions (remediation without prior investigation) or redundant commands.
- **Terminal Grade (G in [0, 1]):** Calculated at episode termination based on the normalized efficiency score:
  G = max(0, Success - (Steps * ws) - (Cost * wc) - (Downtime * wd))

---

## 4. Evaluation Criteria

The environment is designed to provide a robust signal for policy evaluation across several critical metrics:

### 1. Reasoning Gap (Policy Differentiation)
A valid environment must show significant performance variance between heuristic and learned policies.
- **Random Baseline:** ~0.05 (Captures only trivial, accidental resolutions).
- **Rule-Based Baseline:** ~0.35 (Solves easy/medium tasks with high step counts).
- **Optimal Frontier (LLM/PPO):** ~0.75+ (Demonstrates efficient, cost-aware root cause analysis).

### 2. Reward Stationarity and Signal-to-Noise
The dense reward signals are strictly tied to the causal path of the incident. This ensures that the credit assignment problem is solvable even with the 15-step horizon, as agents receive feedback on partial progress (e.g., identifying the correct service).

### 3. Task Entropy and Generalization
The three tasks (Easy, Medium, Hard) provide increasing levels of "incident noise" and service inter-dependencies. A high-quality agent must generalize across these scenarios rather than overfit to specific service names.

### 4. Normalized Convergence
All episode grades are clamped to the `[0.0, 1.0]` range, providing a stable target for regression or reinforcement learning objectives.

---

## 5. Usage and Validation

### Validation
To ensure the environment satisfies the OpenEnv specification:
```bash
openenv validate
```

### Execution
Run the baseline inference script to generate standardized execution logs:
```bash
uv run python inference.py
```

*Note: Environment variables `OPENAI_API_KEY`, `API_BASE_URL`, and `MODEL_NAME` must be configured for LLM-based evaluation.*
