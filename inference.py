# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.

"""
Inference Benchmark Runner for the DevOps Incident Management Environment.
Executes diagnostic and remediation scenarios across predefined control systems. Emits structurally compliant OpenEnv evaluation traces.
"""

import os
import asyncio
import random
import json
from typing import List, Optional
from openai import OpenAI

API_BASE_URL: str = os.getenv("API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME: str = os.getenv("MODEL_NAME", "gpt-4o")

# Fallback to local huggingface-cli cache if the env var isn't explicitly set
try:
    from huggingface_hub import get_token
    fallback_token = get_token()
except ImportError:
    fallback_token = None

HF_TOKEN: Optional[str] = os.getenv("HF_TOKEN") or fallback_token

if HF_TOKEN is None:
    raise ValueError("HF_TOKEN environment variable (or huggingface-cli login) is required")

try:
    from models import DevOpsAction, DevOpsObservation  # type: ignore
except ImportError:
    from my_env.models import DevOpsAction, DevOpsObservation  # type: ignore

BENCHMARK = "DevOps"
TEMPERATURE = 0.0
MAX_TOKENS = 512
MAX_STEPS = 15

SYSTEM_INSTRUCTION = """
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

Respond ONLY with a valid JSON object. No explanation.
Example: {"command": "get_logs", "target": "database", "args": "ERROR"}
"""

def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str] = None) -> None:
    action_clean = action.strip().replace("\n", " ").replace("\r", "")
    done_str = "true" if done else "false"
    error_str = error if error is not None else "null"
    print(f"[STEP] step={step} action={action_clean} reward={reward:.2f} done={done_str} error={error_str}", flush=True)


def log_end(success: bool, steps: int, rewards: List[float]) -> None:
    success_str = "true" if success else "false"
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={success_str} steps={steps} rewards={rewards_str}", flush=True)


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


def build_system_input(step: int, last_obs: DevOpsObservation, last_reward: float, history: List[str]) -> str:
    payload = f"[SRE DASHBOARD] Step: {step}/{MAX_STEPS} | Last Reward: {last_reward:+.2f}\n"
    payload += f"Infrastructure Cost: ${last_obs.total_cost:.2f} | Downtime Penalty: {last_obs.total_downtime:.1f}s\n\n"
    payload += f"ACTIVE INCIDENT: {last_obs.task_description}\n"
    payload += f"ALERTS: {', '.join(last_obs.active_alerts) if last_obs.active_alerts else 'None'}\n\n"
    payload += "SERVICE TOPOLOGY:\n"
    for s in last_obs.services:
        sev_tag = f"[{s.severity.upper()}]" if hasattr(s, "severity") else ""
        payload += f"  {sev_tag} {s.name}: {s.status} | CPU: {s.cpu_usage:.1f}% | Mem: {s.memory_usage:.1f}% | Latency: {s.latency_ms:.0f}ms | Errors: {s.error_rate:.1f}%\n"
    payload += f"\nACTION FEEDBACK:\n{last_obs.action_feedback}\n"
    if history:
        payload += "\nRECENT HISTORY:\n" + "\n".join(history[-4:]) + "\n"
    payload += '\nRespond with JSON: {"command": "...", "target": "...", "args": "..."}'
    return payload


def get_model_action(client: OpenAI, step: int, last_obs: DevOpsObservation, last_reward: float, history: List[str]) -> str:
    user_input = build_system_input(step, last_obs, last_reward, history)
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": user_input},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            stream=False,
            response_format={"type": "json_object"},
        )
        return (completion.choices[0].message.content or "").strip()
    except Exception:
        return json.dumps({"command": "wait", "target": "none"})


async def run_scenario(client: OpenAI, task_id: str, agent_type: str) -> None:
    """Orchestrates one full episode evaluation sequence against the environment."""
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
    last_reward = 0.01

    model_id = MODEL_NAME if agent_type == "llm" else agent_type
    log_start(task=task_id, env=BENCHMARK, model=model_id)

    try:
        obs = env.reset(task_name=task_id)

        for step in range(1, MAX_STEPS + 1):
            if obs.done:
                break

            last_error = None

            if agent_type == "random":
                action_json = get_random_action()
            elif agent_type == "rule-based":
                action_json = get_rule_based_action(obs)
            else:
                action_json = get_model_action(client, step, obs, last_reward, history)

            try:
                action_dict = json.loads(action_json)
                action_obj = DevOpsAction(**action_dict)
            except Exception as parse_err:
                last_error = str(parse_err)
                action_obj = DevOpsAction(command="wait", target="none")
                action_json = json.dumps({"command": "wait", "target": "none"})

            obs = env.step(action_obj)

            reward = obs.reward if obs.reward is not None else 0.01
            done = obs.done

            rewards.append(reward)
            steps_taken = step
            last_reward = reward

            log_step(step=step, action=action_json, reward=reward, done=done, error=last_error)
            history.append(f"Step {step}: {action_json!r} -> reward {reward:+.2f}")

            if done:
                break

        success = bool(env.state_data.get("problem_solved", False))

    except Exception as episode_err:
        last_error = str(episode_err)
        success = False

    finally:
        log_end(success=success, steps=max(1, steps_taken), rewards=[last_reward])


async def main() -> None:
    """Executes the full distributed evaluation curriculum."""
    client = OpenAI(
        base_url=API_BASE_URL,
        api_key=HF_TOKEN,
    )

    for task_name in ["easy", "medium", "hard"]:
        for controller in ["random", "rule-based", "llm"]:
            await run_scenario(client, task_name, controller)


if __name__ == "__main__":
    asyncio.run(main())
