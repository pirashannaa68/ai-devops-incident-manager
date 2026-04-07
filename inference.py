# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.

"""
Inference Benchmark Runner for the DevOps Incident Management Environment (DIME).

This module executes a suite of SRE scenarios (Easy, Medium, Hard) across 
multiple agent types (Random, Rule-based, LLM) using a consistent 
simulation loop and standardized logging format for evaluation.
"""

import os
import asyncio
import random
import json
from typing import List
from openai import OpenAI
from openenv.core.env_server.types import State

# API Configuration and Environment Variables
API_BASE_URL = os.getenv("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o")
HF_TOKEN = os.getenv("HF_TOKEN")

# Authentication Priority: Environment Variable > HuggingFace Token > Local Access
API_KEY = os.getenv("OPENAI_API_KEY") or HF_TOKEN or "local-dev-token"
BENCHMARK = "DevOps"
TEMPERATURE = 0.0
MAX_TOKENS = 512
MAX_STEPS = 15
SUCCESS_SCORE_THRESHOLD = 0.5
MAX_TOTAL_REWARD = 1.0

try:
    from client import get_env_client  # type: ignore
except ImportError:
    pass

from models import DevOpsAction, DevOpsObservation  # type: ignore

IMAGE_NAME = "openenv/my_env_env:latest"

SYSTEM_PROMPT = """
You are a Site Reliability Engineer (SRE) managing a distributed 8-service topology.
The environment simulates dynamic and uncertain incident scenarios.

KEY RULES:
1. Multiple services may exhibit degraded performance simultaneously; prioritize CRITICAL severity services.
2. Remediation actions have tradeoffs:
   - restart_service -> fixes crashes, but incurs a downtime SLA penalty.
   - scale_service   -> mitigates high CPU load, but triples infrastructure cost.
   - rollback_deployment -> resolves faulty deployments, but causes temporary latency.
   - add_db_index    -> addresses latency, but requires 2 steps to take effect.
3. Random secondary failures may occur during an active episode.
4. Repeated identical actions incur a penalty.
5. Infrastructure cost and downtime penalties reduce the episode's overall score.

COMMANDS: "get_logs", "restart_service", "rollback_deployment", "add_db_index", "scale_service", "wait", "finish"
TARGETS: service names (e.g., "auth-api", "payment-gateway", "database", "web-frontend", "redis-cache", "search-index") or table names (e.g., "transactions")
Use `args` with "get_logs" to filter logs (e.g., "ERROR").

Respond ONLY with a valid JSON object. No markdown. No explanation.
Example: {"command": "get_logs", "target": "database", "args": "ERROR"}
"""

def build_user_prompt(step: int, last_obs: DevOpsObservation, last_reward: float, history: List[str]) -> str:
    """
    Constructs the operational context for the SRE agent.
    
    Args:
        step: Current step number.
        last_obs: The most recent system observation.
        last_reward: Reward received from the previous action.
        history: Sequential history of previous (action, reward) pairs.
        
    Returns:
        A structured string containing telemetry, alerts, and system state.
    """
    prompt = f"[SRE DASHBOARD] Step: {step}/{MAX_STEPS} | Last Reward: {last_reward:+.2f}\n"
    prompt += f"Infrastructure Cost Incurred: ${last_obs.total_cost:.2f} | Downtime Penalty: {last_obs.total_downtime:.1f}s\n\n"
    prompt += f"ACTIVE INCIDENT: {last_obs.task_description}\n"
    prompt += f"ALERTS: {', '.join(last_obs.active_alerts) if last_obs.active_alerts else 'None'}\n\n"
    
    prompt += "SERVICE TOPOLOGY:\n"
    for s in last_obs.services:
        sev_tag = f"[{s.severity.upper()}]" if hasattr(s, 'severity') else ""
        prompt += f"  {sev_tag} {s.name}: {s.status} | CPU: {s.cpu_usage:.1f}% | Mem: {s.memory_usage:.1f}% | Latency: {s.latency_ms:.0f}ms | Errors: {s.error_rate:.1f}%\n"

    prompt += f"\nACTION FEEDBACK:\n{last_obs.action_feedback}\n"

    if history:
        prompt += f"\nRECENT HISTORY:\n" + "\n".join(history[-4:]) + "\n"

    prompt += "\nRespond with JSON: {\"command\": \"...\", \"target\": \"...\", \"args\": \"...\"}"
    return prompt

def log_start(task: str, env: str, model: str):
    """Emits the standardized episode initiation log."""
    print(f"[START] task={task} env={env} model={model}")

def log_step(step: int, action: str, reward: float, done: bool, error: str = None):
    """Emits the standardized per-step transaction log."""
    err_str = f" error={error}" if error else ""
    print(f"[STEP] step={step} action={action} reward={reward:.2f} done={done}{err_str}")

def log_end(success: bool, steps: int, score: float, rewards: List[float], cost: float = 0.0, downtime: float = 0.0):
    """Emits the standardized episode termination log and performance metrics."""
    print(f"[END] success={success} steps={steps} score={score:.2f} rewards={rewards}")
    # Additional SLA metrics for internal analysis
    print(f"[DEBUG] infra_cost={cost:.2f} downtime_penalty={downtime:.1f}", flush=True)

def get_random_action() -> str:
    """Generates a non-deterministic exploratory action for baseline evaluation."""
    commands = ["get_logs", "restart_service", "rollback_deployment", "add_db_index", "scale_service", "wait", "finish"]
    targets = ["auth-api", "payment-gateway", "database", "web-frontend", "redis-cache", "search-index", "notification-worker", "user-profile-api", "transactions"]
    return f'{{"command": "{random.choice(commands)}", "target": "{random.choice(targets)}"}}'

def get_rule_based_action(last_obs: DevOpsObservation) -> str:
    """Heuristic-driven remediation logic targeting high-severity service degradation."""
    critical_degraded = [s for s in last_obs.services if s.status == "degraded" and hasattr(s, 'severity') and s.severity == "critical"]
    any_degraded = [s for s in last_obs.services if s.status == "degraded"]
    
    targets = critical_degraded if critical_degraded else any_degraded
    
    for svc in targets:
        if "database" in svc.name and svc.latency_ms > 1000:
            return '{"command": "get_logs", "target": "database", "args": "WARN"}'
        elif "redis" in svc.name:
            return f'{{"command": "restart_service", "target": "{svc.name}"}}'
        elif "payment" in svc.name:
            return f'{{"command": "get_logs", "target": "{svc.name}", "args": "ERROR"}}'
        elif svc.cpu_usage > 90:
            return f'{{"command": "restart_service", "target": "{svc.name}"}}'
        else:
            return f'{{"command": "get_logs", "target": "{svc.name}"}}'

    for alert in last_obs.active_alerts:
        if "db_index" in alert.lower() or "transactions" in alert.lower():
            return '{"command": "add_db_index", "target": "transactions"}'

    return '{"command": "wait", "target": "none"}'

def get_model_action(client: OpenAI, step: int, last_obs: DevOpsObservation, last_reward: float, history: List[str]) -> str:
    """Invokes the language model to analyze telemetry and derive a causal remediation action."""
    user_prompt = build_user_prompt(step, last_obs, last_reward, history)
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            stream=False,
            response_format={"type": "json_object"}
        )
        return (completion.choices[0].message.content or "").strip()
    except Exception:
        return '{"command": "wait", "target": "none"}'

async def run_scenario(client: OpenAI, task_id: str, agent_type: str):
    """
    Orchestrates the interaction loop between the agent and the MyEnvironment instance.
    """
    from server.my_env_environment import MyEnvironment  # type: ignore
    env = MyEnvironment()

    history: List[str] = []
    rewards: List[float] = []
    steps_taken = 0
    score = 0.0
    success = False
    final_cost = 0.0
    final_downtime = 0.0

    model_id = agent_type if agent_type != "llm" else MODEL_NAME
    log_start(task=task_id, env=BENCHMARK, model=model_id)

    try:
        obs = env.reset(task_name=task_id)
        last_reward = 0.0

        for step in range(1, MAX_STEPS + 1):
            if obs.done:
                break

            if agent_type == "random":
                action_json = get_random_action()
            elif agent_type == "rule-based":
                action_json = get_rule_based_action(obs)
            else:
                action_json = get_model_action(client, step, obs, last_reward, history)

            try:
                action_dict = json.loads(action_json)
                action_obj = DevOpsAction(**action_dict)
            except Exception:
                action_obj = DevOpsAction(command="wait", target="none")

            obs = env.step(action_obj)

            reward = obs.reward or 0.0
            done = obs.done

            rewards.append(reward)
            steps_taken = step
            last_reward = reward
            final_cost = obs.total_cost
            final_downtime = obs.total_downtime

            log_step(step=step, action=action_json, reward=reward, done=done)
            history.append(f"Step {step}: {action_json!r} -> reward {reward:+.2f}")

            if done:
                break

        score = sum(rewards) / MAX_TOTAL_REWARD if MAX_TOTAL_REWARD > 0 else 0.0
        score = min(max(score, 0.0), 1.0)
        success = score >= SUCCESS_SCORE_THRESHOLD

    finally:
        log_end(success=success, steps=steps_taken, score=score, rewards=rewards, cost=final_cost, downtime=final_downtime)

async def main() -> None:
    """Main benchmark entry point."""
    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

    # Sequential execution of the curriculum across all agent paradigms
    for task_name in ["easy", "medium", "hard"]:
        for agent in ["random", "rule-based", "llm"]:
            await run_scenario(client, task_name, agent)

if __name__ == "__main__":
    asyncio.run(main())

