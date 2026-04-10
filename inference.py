# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.

"""
Inference Benchmark Runner for the DevOps Incident Management Environment (DIME).

Runs easy/medium/hard SRE scenarios against random, rule-based, and LLM agents.
Emits [START], [STEP], [END] lines compliant with the OpenEnv evaluation spec.
"""

import os
import asyncio
import random
import json
from typing import List, Optional
from openai import OpenAI

# ---------------------------------------------------------------------------
# Environment Variables  (per OpenEnv hackathon spec)
# ---------------------------------------------------------------------------
API_BASE_URL: str = os.getenv("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME: str = os.getenv("MODEL_NAME", "gpt-4o")
HF_TOKEN: Optional[str] = os.getenv("HF_TOKEN")

if HF_TOKEN is None:
    raise ValueError("HF_TOKEN environment variable is required")

# ---------------------------------------------------------------------------
# Model imports (try/except for Docker vs local path differences)
# ---------------------------------------------------------------------------
try:
    from models import DevOpsAction, DevOpsObservation  # type: ignore
except ImportError:
    from my_env.models import DevOpsAction, DevOpsObservation  # type: ignore

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BENCHMARK = "DevOps"
TEMPERATURE = 0.0
MAX_TOKENS = 512
MAX_STEPS = 15

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

# ---------------------------------------------------------------------------
# Log helpers — EXACT format required by OpenEnv evaluation spec
# [START] task=<task_name> env=<benchmark> model=<model_name>
# [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
# [END]   success=<true|false> steps=<n> rewards=<r1,r2,...,rn>
# ---------------------------------------------------------------------------

def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str] = None) -> None:
    # Collapse action to single line (no embedded newlines)
    action_clean = action.strip().replace("\n", " ").replace("\r", "")
    done_str = "true" if done else "false"
    error_str = error if error is not None else "null"
    print(f"[STEP] step={step} action={action_clean} reward={reward:.2f} done={done_str} error={error_str}", flush=True)


def log_end(success: bool, steps: int, rewards: List[float]) -> None:
    success_str = "true" if success else "false"
    # rewards: comma-separated, 2 decimal places, NO brackets
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={success_str} steps={steps} rewards={rewards_str}", flush=True)


# ---------------------------------------------------------------------------
# Agent action generators
# ---------------------------------------------------------------------------

def get_random_action() -> str:
    commands = ["get_logs", "restart_service", "rollback_deployment", "add_db_index", "scale_service", "wait", "finish"]
    targets = ["auth-api", "payment-gateway", "database", "web-frontend", "redis-cache", "search-index", "notification-worker", "user-profile-api", "transactions"]
    return json.dumps({"command": random.choice(commands), "target": random.choice(targets)})


def get_rule_based_action(last_obs: DevOpsObservation) -> str:
    critical_degraded = [s for s in last_obs.services if s.status == "degraded" and hasattr(s, "severity") and s.severity == "critical"]
    any_degraded = [s for s in last_obs.services if s.status == "degraded"]
    targets = critical_degraded if critical_degraded else any_degraded

    for svc in targets:
        if "database" in svc.name and svc.latency_ms > 1000:
            return json.dumps({"command": "get_logs", "target": "database", "args": "WARN"})
        elif "redis" in svc.name:
            return json.dumps({"command": "restart_service", "target": svc.name})
        elif "payment" in svc.name:
            return json.dumps({"command": "get_logs", "target": svc.name, "args": "ERROR"})
        elif svc.cpu_usage > 90:
            return json.dumps({"command": "restart_service", "target": svc.name})
        else:
            return json.dumps({"command": "get_logs", "target": svc.name})

    for alert in last_obs.active_alerts:
        if "db_index" in alert.lower() or "transactions" in alert.lower():
            return json.dumps({"command": "add_db_index", "target": "transactions"})

    return json.dumps({"command": "wait", "target": "none"})


def build_user_prompt(step: int, last_obs: DevOpsObservation, last_reward: float, history: List[str]) -> str:
    prompt = f"[SRE DASHBOARD] Step: {step}/{MAX_STEPS} | Last Reward: {last_reward:+.2f}\n"
    prompt += f"Infrastructure Cost: ${last_obs.total_cost:.2f} | Downtime Penalty: {last_obs.total_downtime:.1f}s\n\n"
    prompt += f"ACTIVE INCIDENT: {last_obs.task_description}\n"
    prompt += f"ALERTS: {', '.join(last_obs.active_alerts) if last_obs.active_alerts else 'None'}\n\n"
    prompt += "SERVICE TOPOLOGY:\n"
    for s in last_obs.services:
        sev_tag = f"[{s.severity.upper()}]" if hasattr(s, "severity") else ""
        prompt += f"  {sev_tag} {s.name}: {s.status} | CPU: {s.cpu_usage:.1f}% | Mem: {s.memory_usage:.1f}% | Latency: {s.latency_ms:.0f}ms | Errors: {s.error_rate:.1f}%\n"
    prompt += f"\nACTION FEEDBACK:\n{last_obs.action_feedback}\n"
    if history:
        prompt += "\nRECENT HISTORY:\n" + "\n".join(history[-4:]) + "\n"
    prompt += '\nRespond with JSON: {"command": "...", "target": "...", "args": "..."}'
    return prompt


def get_model_action(client: OpenAI, step: int, last_obs: DevOpsObservation, last_reward: float, history: List[str]) -> str:
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
            response_format={"type": "json_object"},
        )
        return (completion.choices[0].message.content or "").strip()
    except Exception:
        return json.dumps({"command": "wait", "target": "none"})


# ---------------------------------------------------------------------------
# Main episode runner
# ---------------------------------------------------------------------------

async def run_scenario(client: OpenAI, task_id: str, agent_type: str) -> None:
    """Orchestrates one full episode between agent and MyEnvironment."""
    try:
        from server.my_env_environment import MyEnvironment  # type: ignore
    except ImportError:
        from my_env_environment import MyEnvironment  # type: ignore

    env = MyEnvironment()

    history: List[str] = []
    rewards: List[float] = []
    steps_taken = 0
    success = False
    last_error: Optional[str] = None

    model_id = MODEL_NAME if agent_type == "llm" else agent_type
    log_start(task=task_id, env=BENCHMARK, model=model_id)

    try:
        obs = env.reset(task_name=task_id)
        last_reward = 0.0

        for step in range(1, MAX_STEPS + 1):
            if obs.done:
                break

            last_error = None

            # --- choose action ---
            if agent_type == "random":
                action_json = get_random_action()
            elif agent_type == "rule-based":
                action_json = get_rule_based_action(obs)
            else:
                action_json = get_model_action(client, step, obs, last_reward, history)

            # --- parse and apply action ---
            try:
                action_dict = json.loads(action_json)
                action_obj = DevOpsAction(**action_dict)
            except Exception as parse_err:
                last_error = str(parse_err)
                action_obj = DevOpsAction(command="wait", target="none")
                action_json = json.dumps({"command": "wait", "target": "none"})

            obs = env.step(action_obj)

            reward = obs.reward if obs.reward is not None else 0.0
            done = obs.done

            rewards.append(reward)
            steps_taken = step
            last_reward = reward

            log_step(step=step, action=action_json, reward=reward, done=done, error=last_error)
            history.append(f"Step {step}: {action_json!r} -> reward {reward:+.2f}")

            if done:
                break

        # Ground-truth success from the environment
        success = bool(env.state_data.get("problem_solved", False))

    except Exception as episode_err:
        last_error = str(episode_err)
        success = False

    finally:
        # [END] always emitted, even on exception
        log_end(success=success, steps=steps_taken, rewards=rewards)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    """Run the full evaluation curriculum: 3 tasks × 3 agent types."""
    client = OpenAI(
        base_url=API_BASE_URL,
        api_key=HF_TOKEN,  # HF_TOKEN used as api_key per spec
    )

    for task_name in ["easy", "medium", "hard"]:
        for agent in ["random", "rule-based", "llm"]:
            await run_scenario(client, task_name, agent)


if __name__ == "__main__":
    asyncio.run(main())
