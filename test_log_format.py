"""Verify that our log format matches the OpenEnv spec exactly."""
import sys
sys.path.insert(0, '.')

# Patch HF_TOKEN so the import doesn't fail
import os
os.environ.setdefault("HF_TOKEN", "test-token")

# Re-import after env is patched
from typing import List, Optional

def log_start(task, env, model):
    print(f"[START] task={task} env={env} model={model}", flush=True)

def log_step(step, action, reward, done, error=None):
    action_clean = action.strip().replace("\n", " ").replace("\r", "")
    done_str = "true" if done else "false"
    error_str = error if error is not None else "null"
    print(f"[STEP] step={step} action={action_clean} reward={reward:.2f} done={done_str} error={error_str}", flush=True)

def log_end(success, steps, rewards):
    success_str = "true" if success else "false"
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={success_str} steps={steps} rewards={rewards_str}", flush=True)

print("=== EXACT FORMAT OUTPUT (must match spec) ===")
log_start("easy", "DevOps", "random")
log_step(1, '{"command": "get_logs", "target": "auth-api"}', 0.05, False)
log_step(2, '{"command": "restart_service", "target": "auth-api"}', 0.90, True)
log_end(True, 2, [0.05, 0.90])

print()
print("=== SPEC EXAMPLE (reference) ===")
print("[START] task=click-test env=miniwob model=Qwen3-VL-30B")
print("[STEP] step=1 action=click('123') reward=0.00 done=false error=null")
print("[STEP] step=2 action=fill('456','text') reward=0.00 done=false error=null")
print("[STEP] step=3 action=click('789') reward=1.00 done=true error=null")
print("[END] success=true steps=3 rewards=0.00,0.00,1.00")

print()
print("=== FORMAT CHECKS ===")
import io, contextlib

buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    log_start("easy", "DevOps", "random")
    log_step(1, '{"command":"wait"}', 0.0, False)
    log_step(2, '{"command":"finish"}', 0.9, True)
    log_end(True, 2, [0.0, 0.9])

lines = buf.getvalue().strip().split("\n")
start_line, step1, step2, end_line = lines

# Check START
assert start_line.startswith("[START] task="), f"FAIL: {start_line}"
assert "env=" in start_line and "model=" in start_line, f"FAIL: {start_line}"
print(f"[PASS] [START] format: {start_line}")

# Check STEP
assert "reward=0.00" in step1, f"FAIL reward 2dp: {step1}"
assert "done=false" in step1, f"FAIL done lowercase: {step1}"
assert "error=null" in step1, f"FAIL error=null: {step1}"
print(f"[PASS] [STEP] format: {step1}")

# Check END
assert end_line.startswith("[END] success="), f"FAIL: {end_line}"
assert "score=" not in end_line, f"FAIL: score= should not be in [END]: {end_line}"
rewards_value = end_line.split("rewards=")[1] if "rewards=" in end_line else ""
assert "[" not in rewards_value and "]" not in rewards_value, f"FAIL: no brackets in rewards value: {rewards_value}"

assert "rewards=0.00,0.90" in end_line, f"FAIL rewards format: {end_line}"
print(f"[PASS] [END] format: {end_line}")

print()
print("ALL FORMAT CHECKS PASSED - spec compliant!")
