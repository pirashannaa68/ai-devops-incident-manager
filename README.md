# DevOps Incident Management Environment (DIME)

Professional Site Reliability Engineering simulation for evaluating reinforcement learning agents in complex distributed systems.

## 1. Project Overview
The DevOps Incident Management Environment (DIME) provides a high-fidelity simulation of an 8-service distributed microservice topology. It models a production-grade infrastructure, complete with real-time telemetry, service logs, and a causal failure graph. The environment serves as a platform for training and evaluating agents on complex, real-world Site Reliability Engineering (SRE) incident response tasks.

## 2. Motivation
Modern distributed systems exhibit emergent failure modes that are difficult to model in static environments. DIME captures the core challenges of SRE work:
- **Uncertainty**: Agents must disambiguate true failure signals from noise across high-volume telemetry.
- **Trade-offs**: Every remediation action (e.g., scaling or restarting) incurs infrastructural costs or Service Level Agreement (SLA) penalties.
- **Cascading Dependencies**: Failures in downstream services (e.g., databases) propagate through the system, requiring root cause identification within a complex dependency tree.

## 3. System Architecture
The system implements a standard request-response loop between an agent and a simulated environment:
- **Environment Server**: A FastAPI-based backend that manages the Markov Decision Process (MDP) state transitions (`MyEnvironment`).
- **Data Models**: Pydantic-typed schemas ensure strictly-typed communication via the `DevOpsAction` and `DevOpsObservation` models.
- **Inference Runner**: An execution script (`inference.py`) that coordinates agent interaction and logs performance metrics.

## 4. Environment Design

### Observation Space
The `DevOpsObservation` model provides a granular view of the system state:
- **Service Metrics**: CPU usage, memory usage, latency (ms), and error rates for all 8 microservices.
- **Active Alerts**: A list of high-priority system alerts (e.g., "CRITICAL: High CPU on auth-api").
- **Cost & SLA Tracking**: Real-time accumulation of infrastructural burn-rate and cumulative downtime penalties.
- **Action Feedback**: Direct output from diagnostic commands (e.g., filtered log snippets).

### Action Space
Agents interact with the environment via a discrete set of commands:
- `get_logs`: Retrieve and filter logs for a specific service.
- `restart_service`: Power-cycle a service to clear transient errors (incurs downtime).
- `rollback_deployment`: Revert to a previous stable version (resolves configuration errors).
- `add_db_index`: Address query latency (requires 2 steps for completion).
- `scale_service`: Horizontally scale resources to mitigate load (triples cost-per-minute).
- `wait`: Observe the system for one step without taking action.
- `finish`: Terminate the episode once the incident is resolved.

### Reward Function
The reward function balances resolution speed, cost-efficiency, and system availability:
- **Resolution Success**: Large positive signal upon verified problem resolution.
- **Step Penalty**: Small negative signal per step to encourage efficient diagnosis.
- **Cost Penalty**: Negative signal proportional to the infrastructure burn-rate.
- **Downtime Penalty**: Cumulative penalty for services in a 'degraded' or 'down' state.

## 5. Task Design
The environment includes three primary scenarios with increasing complexity:
- **Easy**: Isolate and resolve a CPU spike on a single service (`auth-api`) through direct intervention.
- **Medium**: Triage a multi-incident failure involving a faulty deployment and secondary service degradation.
- **Hard**: Diagnose cascading database latency causing upstream availability issues, while managing resource constraints.
- **Stochasticity**: A chaos engine periodically introduces random secondary faults to healthy services to simulate "noisy" production environments.

## 6. Expected Outputs
- **Interaction Format**: All actions and observations are exchanged as structured JSON objects.
- **Logging Standards**: The system emits standardized logs to `stdout` for automated scoring:
  - `[START] task={task_name} env={env_id} model={model_id}`
  - `[STEP] step={n} action={json} reward={r} done={bool}`
  - `[END] success={bool} steps={n} score={0.0-1.0} rewards={list}`

## 7. Evaluation Criteria
### Environment Integrity
- **Realism**: Alignment of failure modes with real-world SRE scenarios.
- **Consistency**: Reproducibility of state transitions across episodes.
- **Learnability**: Clarity of the reward signal for reinforcement learning.

### Agent Performance
- **Success Rate**: Frequency of verified incident resolution within step limits.
- **Resource Efficiency**: Total steps taken to reach resolution.
- **Economic Impact**: Minimization of cumulative infrastructure cost and downtime penalties.

## 8. Baseline Performance
Expected outcomes based on standard agent implementations:
- **Random Agent**: Score ≈ 0.01. Primarily fails due to random exploration without resolution.
- **Rule-based Agent**: Score ≈ 0.40 - 0.60. Successfully resolves simple deterministic scenarios but struggles with cascading failures.
- **State-of-the-art Agent**: Score ≈ 0.85+. Demonstrates causal reasoning and cost-aware remediation.

## 9. Setup Instructions
### Installation
1. Ensure Python 3.10+ is installed.
2. Initialize the environment:
   ```bash
   uv sync
   # or
   pip install -e .
   ```

### Docker Support
Build the production image for isolated evaluation:
```bash
docker build -t openenv/my_env_env:latest .
```

## 10. Usage Instructions
### Starting the Environment
Run the FastAPI server locally:
```bash
python -m server.app
```

### Running the Agent
Execute the inference benchmark across all scenarios:
```bash
python inference.py
```

### Validation
Verify the environment specification:
```bash
openenv validate
```
