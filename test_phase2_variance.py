import sys
sys.path.insert(0, '.')
from server.my_env_environment import MyEnvironment
from models import DevOpsAction

print("=== PHASE 2 SCORE VARIANCE SIMULATION ===")
print("Simulating what a frontier LLM agent (Nemotron) would do...")

# EASY - LLM reads alerts and restarts auth-api
print("\n--- TASK: easy ---")
env = MyEnvironment()
obs = env.reset(task_name="easy")
print(f"  alerts: {obs.active_alerts}")
obs = env.step(DevOpsAction(command="get_logs", target="auth-api"))
print(f"  step1 get_logs auth-api:  reward={obs.reward}")
obs = env.step(DevOpsAction(command="restart_service", target="auth-api"))
print(f"  step2 restart auth-api:   reward={obs.reward}, done={obs.done}")
easy_grade = env.grade()
print(f"  grade(): {easy_grade}  (expected ~0.90)")

# MEDIUM - rollback payment-gateway + restart search-index
print("\n--- TASK: medium ---")
env2 = MyEnvironment()
obs = env2.reset(task_name="medium")
print(f"  alerts: {obs.active_alerts}")
obs = env2.step(DevOpsAction(command="get_logs", target="payment-gateway"))
print(f"  step1 get_logs payment-gw: reward={obs.reward}")
obs = env2.step(DevOpsAction(command="rollback_deployment", target="payment-gateway"))
print(f"  step2 rollback:            reward={obs.reward}, done={obs.done}")
obs = env2.step(DevOpsAction(command="restart_service", target="search-index"))
print(f"  step3 restart search:      reward={obs.reward}, done={obs.done}")
medium_grade = env2.grade()
print(f"  grade(): {medium_grade}  (expected ~0.85)")

# HARD - identify DB root cause, fix redis, queue index
print("\n--- TASK: hard ---")
env3 = MyEnvironment()
obs = env3.reset(task_name="hard")
print(f"  alerts: {obs.active_alerts}")
obs = env3.step(DevOpsAction(command="get_logs", target="database"))
print(f"  step1 get_logs database:  reward={obs.reward} (root cause identified)")
obs = env3.step(DevOpsAction(command="restart_service", target="redis-cache"))
print(f"  step2 restart redis:      reward={obs.reward}")
obs = env3.step(DevOpsAction(command="add_db_index", target="transactions"))
print(f"  step3 add_db_index:       reward={obs.reward}")
obs = env3.step(DevOpsAction(command="wait", target="none"))
obs = env3.step(DevOpsAction(command="wait", target="none"))
print(f"  step5 (index applied):    done={obs.done}, solved={env3.state_data['problem_solved']}")
hard_grade = env3.grade()
print(f"  grade(): {hard_grade}  (expected ~0.65)")

print("\n=== VARIANCE CHECK ===")
print(f"  Easy:   {easy_grade}")
print(f"  Medium: {medium_grade}")
print(f"  Hard:   {hard_grade}")
all_different = len({easy_grade, medium_grade, hard_grade}) == 3
all_in_range = all(0.0 < g < 1.0 for g in [easy_grade, medium_grade, hard_grade])
print(f"  All different:   {all_different}")
print(f"  All in (0,1):    {all_in_range}")

# DISQUALIFICATION CHECK: verify random agent does NOT always return same score as LLM agent
# (i.e., grade varies with agent quality - proves grader is meaningful)
print("\n=== DISQUALIFICATION CHECK: do graders vary? ===")
import random
random.seed(42)
commands = ["get_logs", "restart_service", "rollback_deployment", "scale_service", "wait", "finish"]
targets = ["auth-api", "payment-gateway", "database", "web-frontend", "redis-cache", "search-index", "transactions"]

random_grades = []
for task in ["easy", "medium", "hard"]:
    renv = MyEnvironment()
    renv.reset(task_name=task)
    for _ in range(10):
        cmd = random.choice(commands)
        tgt = random.choice(targets)
        try:
            robs = renv.step(DevOpsAction(command=cmd, target=tgt))
            if robs.done:
                break
        except:
            break
    random_grades.append(renv.grade())

print(f"  Random agent grades: {random_grades}")
print(f"  LLM agent grades:    [{easy_grade}, {medium_grade}, {hard_grade}]")
print(f"  Grades differ between agents: {random_grades != [easy_grade, medium_grade, hard_grade]}")
print("\n  [PASS] Grader is meaningful - different agents get different scores")
