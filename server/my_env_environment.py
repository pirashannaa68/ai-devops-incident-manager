import copy
import random
from typing import Dict, Any, List
from uuid import uuid4

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

import sys
import os

# Add project root to sys.path to allow robust imports
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from models import DevOpsAction, DevOpsObservation, ServiceStatus

# Background telemetry for healthy services to test observation processing and parsing logic
DISTRACTORS = {
    "user-profile-api": {"status": "running", "severity": "low", "cpu_usage": 5.0, "memory_usage": 15.0, "latency_ms": 12.0, "error_rate": 0.01, "cost_per_minute": 0.1},
    "notification-worker": {"status": "running", "severity": "low", "cpu_usage": 22.0, "memory_usage": 45.0, "latency_ms": 50.0, "error_rate": 0.0, "cost_per_minute": 0.2},
    "redis-cache": {"status": "running", "severity": "medium", "cpu_usage": 8.0, "memory_usage": 80.0, "latency_ms": 1.5, "error_rate": 0.0, "cost_per_minute": 0.4},
    "search-index": {"status": "running", "severity": "low", "cpu_usage": 14.0, "memory_usage": 30.0, "latency_ms": 18.0, "error_rate": 0.05, "cost_per_minute": 0.3},
}

DISTRACTOR_LOGS = {
    "user-profile-api": "2026-04-05T10:00 [INFO] Heartbeat OK.\n2026-04-05T10:01 [INFO] GET /profile/me 200 OK - 12ms",
    "notification-worker": "2026-04-05T10:00 [DEBUG] Batch processed 52 emails.\n2026-04-05T10:01 [INFO] Connected to SMTP relay.",
    "redis-cache": "2026-04-05T10:00 [INFO] BGREWRITEAOF starting.\n2026-04-05T10:01 [INFO] Background append only file rewrite terms successful.",
    "search-index": "2026-04-05T10:00 [INFO] Cluster state green.\n2026-04-05T10:01 [DEBUG] Indexing 120 documents."
}

# Initial states for the 3 tasks
EASY_STATE = {
    "task_name": "easy",
    "description": "On-call Pager: HIGH CPU utilization detected on auth-api. API latency is increasing.",
    "alerts": ["CRITICAL: High CPU on auth-api (99%)"],
    "services": {
        "web-frontend": {"status": "running", "severity": "critical", "cpu_usage": 15.0, "memory_usage": 32.0, "latency_ms": 25.0, "error_rate": 0.01, "cost_per_minute": 1.0},
        "auth-api": {"status": "degraded", "severity": "critical", "cpu_usage": 99.5, "memory_usage": 65.0, "latency_ms": 1540.0, "error_rate": 2.5, "cost_per_minute": 0.5},
        "payment-gateway": {"status": "running", "severity": "critical", "cpu_usage": 10.0, "memory_usage": 40.0, "latency_ms": 50.0, "error_rate": 0.0, "cost_per_minute": 2.5},
        "database": {"status": "running", "severity": "critical", "cpu_usage": 35.0, "memory_usage": 55.0, "latency_ms": 5.0, "error_rate": 0.0, "cost_per_minute": 3.0},
        **DISTRACTORS
    },
    "logs": {
        "auth-api": "2026-04-05T09:59 [INFO] Server started.\n2026-04-05T10:00 [WARN] ThreadPool exhausted.\n2026-04-05T10:01 [ERROR] Request queue full, dropping connects. High CPU lock.",
        "web-frontend": "2026-04-05T09:59 [INFO] Serving asset main.js.\n2026-04-05T10:01 [WARN] auth-api taking >1000ms to respond.",
        "payment-gateway": "2026-04-05T10:00 [INFO] Payment ping OK.",
        "database": "2026-04-05T10:00 [INFO] Connection pool healthy.",
        **DISTRACTOR_LOGS
    },
    "problem_solved": False,
    "progress": {"checked_logs": False}
}

# Task definition: Multi-incident failure with concurrent deployment errors and disk alerts
MEDIUM_STATE = {
    "task_name": "medium",
    "description": "On-call Pager: Elevated Error Rate on payment-gateway following a recent deployment. Search-index is also alerting.",
    "alerts": ["CRITICAL: High Error Rate on payment-gateway (15%)", "WARN: search-index cluster status red"],
    "services": {
        "web-frontend": {"status": "running", "severity": "critical", "cpu_usage": 20.0, "memory_usage": 35.0, "latency_ms": 30.0, "error_rate": 1.5, "cost_per_minute": 1.0},
        "auth-api": {"status": "running", "severity": "critical", "cpu_usage": 15.0, "memory_usage": 40.0, "latency_ms": 20.0, "error_rate": 0.0, "cost_per_minute": 0.5},
        "payment-gateway": {"status": "degraded", "severity": "critical", "cpu_usage": 12.0, "memory_usage": 45.0, "latency_ms": 65.0, "error_rate": 15.5, "cost_per_minute": 2.5},
        "database": {"status": "running", "severity": "critical", "cpu_usage": 25.0, "memory_usage": 50.0, "latency_ms": 6.0, "error_rate": 0.0, "cost_per_minute": 3.0},
        **DISTRACTORS
    },
    "logs": {
        "payment-gateway": "2026-04-05T09:59 [INFO] Container initializing.\n2026-04-05T10:00 [INFO] Deployment v2.1 finished.\n2026-04-05T10:01 [ERROR] TypeError: missing payment secret config key. Failed to process transaction.",
        "web-frontend": "2026-04-05T10:00 [INFO] Client rendering profile.\n2026-04-05T10:01 [ERROR] Payment failed: 500 Internal Server Error from payment-gateway.",
        "search-index": "2026-04-05T09:59 [WARN] Disk space critical.\n2026-04-05T10:01 [ERROR] Failed to write shard.",
        "auth-api": "2026-04-05T10:00 [INFO] JWT validated.",
        "database": "2026-04-05T10:00 [INFO] Connections at 10%.",
        **{k:v for k,v in DISTRACTOR_LOGS.items() if k != "search-index"}
    },
    "problem_solved": False,
    "progress": {"checked_logs": False, "search_fixed": False}
}

# Task definition: Cascading database latency affecting upstream frontends and concurrent cache exhaustion
HARD_STATE = {
    "task_name": "hard",
    "description": "On-call Pager: web-frontend timeout spike. Database alerts firing. Redis cache memory exhausted.",
    "alerts": ["CRITICAL: web-frontend Response Time > 5000ms", "WARN: database connection pool filling up", "CRITICAL: redis OOM"],
    "services": {
        "web-frontend": {"status": "degraded", "severity": "critical", "cpu_usage": 45.0, "memory_usage": 60.0, "latency_ms": 5200.0, "error_rate": 12.0, "cost_per_minute": 1.0},
        "auth-api": {"status": "running", "severity": "critical", "cpu_usage": 15.0, "memory_usage": 40.0, "latency_ms": 20.0, "error_rate": 0.0, "cost_per_minute": 0.5},
        "payment-gateway": {"status": "running", "severity": "critical", "cpu_usage": 12.0, "memory_usage": 45.0, "latency_ms": 65.0, "error_rate": 0.0, "cost_per_minute": 2.5},
        "database": {"status": "degraded", "severity": "critical", "cpu_usage": 88.0, "memory_usage": 90.0, "latency_ms": 4800.0, "error_rate": 1.5, "cost_per_minute": 3.0},
        **DISTRACTORS
    },
    "logs": {
        "web-frontend": "2026-04-05T09:59 [INFO] Metric collection tick.\n2026-04-05T10:00 [ERROR] Timeout waiting for DB query from transactions service.\n2026-04-05T10:01 [ERROR] /checkout endpoint failed: 504 Gateway Timeout.",
        "database": "2026-04-05T09:59 [INFO] Checkpoint written.\n2026-04-05T10:00 [WARN] Slow query detected on transactions table. Execution time: 5.2s. Missing index on user_id.\n2026-04-05T10:01 [WARN] CPU spiking due to full table scans.",
        "redis-cache": "2026-04-05T10:00 [WARN] Memory approaching limit.\n2026-04-05T10:01 [ERROR] OOM command not allowed when used memory > 'maxmemory'.",
        "payment-gateway": "2026-04-05T10:00 [INFO] Payment ping OK.",
        "auth-api": "2026-04-05T10:00 [INFO] JWT validated.",
        **{k:v for k,v in DISTRACTOR_LOGS.items() if k != "redis-cache"}
    },
    "problem_solved": False,
    "progress": {"checked_frontend_logs": False, "checked_db_logs": False, "identified_root": False, "redis_fixed": False}
}

def get_service_objects(services_dict: Dict) -> List[ServiceStatus]:
    return [
        ServiceStatus(
            name=name,
            status=info["status"],
            severity=info["severity"],
            cpu_usage=info["cpu_usage"],
            memory_usage=info["memory_usage"],
            latency_ms=info["latency_ms"],
            error_rate=info["error_rate"],
            cost_per_minute=info["cost_per_minute"]
        ) for name, info in services_dict.items()
    ]


class MyEnvironment(Environment):
    """
    DevOps Incident Manager Environment.

    A reinforcement learning environment simulating a distributed microservice topology.
    Manages the Markov state transitions, reward logic, and action processing for an SRE agent.
    """
    SUPPORTS_CONCURRENT_SESSIONS: bool = True
    MAX_STEPS = 15

    def __init__(self):
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self.state_data = copy.deepcopy(EASY_STATE)
        self.task_name = "easy"
        self.total_reward = 0.0
        self.last_action_str = ""
        
        # New Chaos Mechanics
        self.total_cost = 0.0
        self.total_downtime = 0.0
        self.delayed_tasks = []

    def reset(self, task_name: str = "easy") -> DevOpsObservation:
        """
        Resets the environment state based on the designated curriculum task.
        """
        self._state = State(episode_id=str(uuid4()), step_count=0)
        self.task_name = task_name
        self.total_reward = 0.0
        self.last_action_str = ""
        self.total_cost = 0.0
        self.total_downtime = 0.0
        self.delayed_tasks = []
        
        if task_name == "easy":
            self.state_data = copy.deepcopy(EASY_STATE)
        elif task_name == "medium":
            self.state_data = copy.deepcopy(MEDIUM_STATE)
        elif task_name == "hard":
            self.state_data = copy.deepcopy(HARD_STATE)
        else:
            self.state_data = copy.deepcopy(EASY_STATE)

        return DevOpsObservation(
            task_description=self.state_data["description"],
            active_alerts=self.state_data["alerts"],
            services=get_service_objects(self.state_data["services"]),
            action_feedback="Environment initialized. Awaiting diagnostic commands.",
            step_count=0,
            total_cost=0.0,
            total_downtime=0.0,
            done=False,
            reward=0.0
        )

    def trigger_chaos(self):
        """Randomly introduce failures to healthy systems mid-incident."""
        healthy_targets = [k for k, v in self.state_data["services"].items() if v["status"] == "running"]
        if not healthy_targets:
            return
        
        victim = random.choice(healthy_targets)
        chaos_events = ["cpu_spike", "memory_leak", "latency_jitter"]
        event = random.choice(chaos_events)
        
        svc = self.state_data["services"][victim]
        svc["status"] = "degraded"
        
        if event == "cpu_spike":
            svc["cpu_usage"] = min(100.0, svc["cpu_usage"] + 60.0)
            self.state_data["alerts"].append(f"CHAOS EVENT: cpu_spike on {victim}")
        elif event == "memory_leak":
            svc["memory_usage"] = min(100.0, svc["memory_usage"] + 75.0)
            self.state_data["alerts"].append(f"CHAOS EVENT: memory_leak on {victim}")
        elif event == "latency_jitter":
            svc["latency_ms"] = svc["latency_ms"] * 5.0
            self.state_data["alerts"].append(f"CHAOS EVENT: latency_jitter on {victim}")

    def grade(self) -> float:
        """
        Computes the final episode grade incorporating resolution status and SLA-based penalties.
        Normalized to the [0.0, 1.0] range.
        """
        success = 1.0 if self.state_data["problem_solved"] else 0.0
        
        # Penalties calculation
        step_penalty = (self._state.step_count * 0.03)
        cost_penalty = (self.total_cost * 0.01)
        downtime_penalty = (self.total_downtime * 0.02)
        
        raw_score = success - step_penalty - cost_penalty - downtime_penalty
        return max(0.0, round(raw_score, 2))

    def step(self, action: DevOpsAction) -> DevOpsObservation:  # type: ignore[override]
        """
        Applies the provided action, executes Markov state transitions, and calculates the reward.
        """
        self._state.step_count += 1
        reward = 0.0
        feedback = ""
        done = False
        
        # 1. Increment SLAs
        for svc in self.state_data["services"].values():
            self.total_cost += svc["cost_per_minute"]
            if svc["status"] != "running":
                weight = 2.0 if svc["severity"] == "critical" else 1.0
                self.total_downtime += weight

        # 2. Chaos Generator (15% chance of random secondary failure)
        if random.random() < 0.15:
            self.trigger_chaos()
            feedback += "\n[ALERT] A new intermittent issue has appeared. Check active alerts.\n"

        # 3. Process Delayed Tasks (Partial Fixes over time)
        tasks_to_keep = []
        for task in self.delayed_tasks:
            task["delay"] -= 1
            if task["delay"] <= 0:
                # Apply partial fix for DB index
                if task["action"] == "add_db_index" and task["target"] == "transactions":
                    self.state_data["problem_solved"] = True
                    svc = self.state_data["services"]["database"]
                    # Slowly cooldown latency (PARTIAL FIX)
                    svc["latency_ms"] = max(5.0, svc["latency_ms"] * 0.25)
                    svc["cpu_usage"] = max(25.0, svc["cpu_usage"] * 0.5)
                    svc["status"] = "running"
                    self.state_data["services"]["web-frontend"]["error_rate"] = max(0.0, self.state_data["services"]["web-frontend"]["error_rate"] - 5.0)
                    feedback += f"\n[DELAYED EVENT] The index applied on {task['target']} is taking effect. DB latency partially cooling down."
            else:
                tasks_to_keep.append(task)
        self.delayed_tasks = tasks_to_keep

        # 4. Markov State Transition: Progressive Degradation
        if not self.state_data["problem_solved"]:
            for name, svc in self.state_data["services"].items():
                if svc["status"] == "degraded":
                    svc["latency_ms"] = round(min(30000.0, svc["latency_ms"] * 1.05), 1)
                    if svc["error_rate"] > 0:
                        svc["error_rate"] = round(min(100.0, svc["error_rate"] + 1.5), 1)
            
            # Causal Graph cascading
            if self.task_name == "hard":
                db_lat = self.state_data["services"]["database"]["latency_ms"]
                self.state_data["services"]["web-frontend"]["latency_ms"] = round(db_lat * 1.08, 1)

        current_action_str = f"{action.command}:{action.target}"

        # Penalize repeated useless action
        if current_action_str == self.last_action_str:
            reward -= 0.1
            feedback = f"Repeated action: {action.command} on {action.target}."
        self.last_action_str = current_action_str

        if self._state.step_count >= self.MAX_STEPS:
            done = True
            feedback += "\nMax steps reached. Shift handover."
            return self._build_obs(feedback, reward, done)

        if action.command == "finish":
            done = True
            if not self.state_data["problem_solved"]:
                feedback += "Finished early without resolving core incidents! Major SLA penalty."
            else:
                feedback += "Incident marked as resolved."
            return self._build_obs(feedback, reward, done)

        # Helper method
        def process_logs(target: str) -> str:
            raw_logs = self.state_data["logs"].get(target, "No logs exist for this target.")
            if action.args:
                filtered = [line for line in raw_logs.split("\n") if action.args.lower() in line.lower()]
                if not filtered:
                    return f"[DEBUG] Grep '{action.args}' returned no results for {target}."
                return "\n".join(filtered)
            return raw_logs

        # ==================================
        # Agent Action Processing
        # ==================================
        if action.command == "get_logs":
            feedback = process_logs(action.target)
            reward += 0.05
            if self.task_name == "hard" and action.target == "database":
                self.state_data["progress"]["identified_root"] = True

        elif action.command == "scale_service":
            # Action Tradeoff: Scale = temporary fix but heavily increases Cost!
            if action.target in self.state_data["services"]:
                svc = self.state_data["services"][action.target]
                svc["cost_per_minute"] *= 3.0  # Spike cost!
                svc["cpu_usage"] = max(10.0, svc["cpu_usage"] * 0.3)
                feedback += f"Scaled {action.target} horizontally. Warning: Burn rate tripled!"
                reward += 0.1
            else:
                feedback += "Target to scale does not exist."

        # -----------------------------
        # EASY LOGIC
        # -----------------------------
        elif self.task_name == "easy":
            if action.command == "restart_service" and action.target == "auth-api":
                self.state_data["problem_solved"] = True
                self.state_data["alerts"] = [a for a in self.state_data["alerts"] if "auth-api" not in a]
                self.state_data["services"]["auth-api"]["cpu_usage"] = 15.0
                self.state_data["services"]["auth-api"]["status"] = "running"
                reward += 0.5
                feedback += "Successfully restarted auth-api. CPU back to normal."
                done = True

        # -----------------------------
        # MEDIUM LOGIC
        # -----------------------------
        elif self.task_name == "medium":
            if action.command == "rollback_deployment" and action.target == "payment-gateway":
                self.state_data["problem_solved"] = True
                self.state_data["alerts"] = [a for a in self.state_data["alerts"] if "payment-gateway" not in a]
                self.state_data["services"]["payment-gateway"]["error_rate"] = 0.0
                self.state_data["services"]["payment-gateway"]["status"] = "running"
                reward += 0.5
                feedback += "Rollback requested on payment-gateway."
                # Don't end immediately unless search index is also fixed (Multi-incident)
                if self.state_data["progress"]["search_fixed"]:
                    done = True
            elif action.command == "restart_service" and action.target == "search-index":
                self.state_data["progress"]["search_fixed"] = True
                self.state_data["services"]["search-index"]["status"] = "running"
                reward += 0.2
                feedback += "Restarted search-index cleanly."
                if self.state_data["problem_solved"]:
                    done = True

        # -----------------------------
        # HARD LOGIC
        # -----------------------------
        elif self.task_name == "hard":
            if action.command == "add_db_index" and action.target == "transactions":
                if not self.state_data["progress"]["identified_root"]:
                    feedback += "Added index blindly! Huge risk taken."
                    reward -= 0.1
                else:
                    feedback += "DB Index task queued (Takes 2 steps to apply natively)."
                # Delayed effect: Add to queue
                self.delayed_tasks.append({"action": action.command, "target": action.target, "delay": 2})
                reward += 0.2
            elif action.command == "restart_service" and action.target == "redis-cache":
                # Flush Redis to fix OOM
                self.state_data["progress"]["redis_fixed"] = True
                self.state_data["services"]["redis-cache"]["memory_usage"] = 5.0
                self.state_data["services"]["redis-cache"]["status"] = "running"
                reward += 0.2
                feedback += "Restarted redis-cache, memory cleared."
            elif action.command == "restart_service" and action.target == "database":
                self.total_downtime += 10.0 # Huge downtime penalty
                feedback += "Restarted database. Thundering herd effect. +10s Downtime penalty."

        return self._build_obs(feedback, reward, done)

    def _build_obs(self, feedback: str, reward: float, done: bool = False) -> DevOpsObservation:
        self.total_reward += reward

        if done:
            final_grade = self.grade()
            reward = final_grade - (self.total_reward - reward)

        return DevOpsObservation(
            task_description=self.state_data["description"],
            active_alerts=self.state_data["alerts"],
            services=get_service_objects(self.state_data["services"]),
            action_feedback=feedback,
            step_count=self._state.step_count,
            total_cost=round(self.total_cost, 2),
            total_downtime=round(self.total_downtime, 2),
            done=done,
            reward=reward,
            metadata={"problem_solved": self.state_data["problem_solved"]}
        )

    @property
    def state(self) -> State:
        return self._state
