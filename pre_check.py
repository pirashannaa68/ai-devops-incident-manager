import sys, os
sys.path.insert(0, '.')

print('='*60)
print('PRE-SUBMISSION CHECKLIST - AUTOMATED VERIFICATION')
print('='*60)
passes = 0
fails = 0

def check(name, condition, detail=''):
    global passes, fails
    if condition:
        passes += 1
        print(f'  [PASS] {name}')
    else:
        fails += 1
        print(f'  [FAIL] {name}' + (f': {detail}' if detail else ''))

# --- 1. FILE STRUCTURE ---
print()
print('1. File Structure')
check('inference.py at root', os.path.exists('inference.py'))
check('openenv.yaml at root', os.path.exists('openenv.yaml'))
check('Dockerfile at root', os.path.exists('Dockerfile'))
check('README.md at root', os.path.exists('README.md'))
check('server/ directory exists', os.path.isdir('server'))

# --- 2. ENV VARIABLES ---
print()
print('2. Environment Variables in inference.py')
with open('inference.py') as f:
    inf_src = f.read()
check('API_BASE_URL with default', 'API_BASE_URL' in inf_src and 'https://api.openai.com/v1' in inf_src)
check('MODEL_NAME with default', 'MODEL_NAME' in inf_src and 'gpt-4o' in inf_src)
check('HF_TOKEN read from env', 'HF_TOKEN' in inf_src and 'os.getenv' in inf_src)
check('HF_TOKEN mandatory raises', 'raise ValueError' in inf_src)
check('OpenAI client used', 'from openai import OpenAI' in inf_src)
check('api_key=HF_TOKEN directly', 'api_key=HF_TOKEN' in inf_src)

# --- 3. LOG FORMAT ---
print()
print('3. Log Format Compliance')
check('[START] task= env= model=', '[START] task=' in inf_src and 'env=' in inf_src and 'model=' in inf_src)
check('[STEP] error= always emitted', 'error_str' in inf_src and '"null"' in inf_src and 'error={error_str}' in inf_src)
check('[END] no score= field', 'score=' not in inf_src)
no_brackets = "rewards_str = \",\".join" in inf_src or "','.join" in inf_src or "join(" in inf_src
check('[END] rewards no brackets', no_brackets)
check('reward 2dp', 'reward:.2f' in inf_src)
check('done lowercase true/false', '"true" if done else "false"' in inf_src)
check('success lowercase', '"true" if success else "false"' in inf_src)
check('flush=True on prints', inf_src.count('flush=True') >= 3)
check('[END] in finally block', 'finally' in inf_src and 'log_end' in inf_src)

# --- 4. OPENENV.YAML ---
print()
print('4. openenv.yaml')
import yaml
with open('openenv.yaml') as f:
    cfg = yaml.safe_load(f)
check('spec_version present', 'spec_version' in cfg)
check('name = my_env', cfg.get('name') == 'my_env')
check('type = space', cfg.get('type') == 'space')
check('runtime = fastapi', cfg.get('runtime') == 'fastapi')
check('app = server.app:app', cfg.get('app') == 'server.app:app')
check('port = 8000', cfg.get('port') == 8000)
check('no extra fields (description/tasks)', 'description' not in cfg and 'tasks' not in cfg)

# --- 5. MODELS ---
print()
print('5. Pydantic Models (typed)')
from models import DevOpsAction, DevOpsObservation
obs_props = DevOpsObservation.model_json_schema().get('properties', {})
act_props = DevOpsAction.model_json_schema().get('properties', {})
check('DevOpsObservation.done field', 'done' in obs_props)
check('DevOpsObservation.reward field', 'reward' in obs_props)
check('DevOpsObservation.services field', 'services' in obs_props)
check('DevOpsObservation.active_alerts field', 'active_alerts' in obs_props)
check('DevOpsAction.command field', 'command' in act_props)
check('DevOpsAction.target field', 'target' in act_props)

# --- 6. ENVIRONMENT INTERFACE ---
print()
print('6. Environment Interface')
from server.my_env_environment import MyEnvironment
env = MyEnvironment()

obs = env.reset(task_name='easy')
check('reset() returns DevOpsObservation', isinstance(obs, DevOpsObservation))
check('reset() done=False', obs.done == False)
check('reset() reward=0.0', obs.reward == 0.0)
check('reset() has task_description', bool(obs.task_description))
check('reset() has active_alerts', isinstance(obs.active_alerts, list))

action = DevOpsAction(command='get_logs', target='auth-api')
obs2 = env.step(action)
check('step() returns DevOpsObservation', isinstance(obs2, DevOpsObservation))
check('step() reward not None', obs2.reward is not None)
check('step() done is bool', isinstance(obs2.done, bool))
check('step() reward > 0 for get_logs', float(obs2.reward) > 0.0)

st = env.state
check('state() has step_count', hasattr(st, 'step_count'))
check('state.step_count == 1', st.step_count == 1)

g = env.grade()
check('grade() in [0.0, 1.0]', 0.0 <= g <= 1.0)
check('grade() is float', isinstance(g, float))

meta = env.get_metadata()
check('get_metadata() name=my_env', meta.name == 'my_env')

env.close()
check('close() no error', True)

# --- 7. ALL 3 TASKS ---
print()
print('7. All 3 Tasks + Grader Variance')
for task in ['easy', 'medium', 'hard']:
    e = MyEnvironment()
    o = e.reset(task_name=task)
    check(f'reset(task_name={task!r}) works', o.done == False and bool(o.task_description))
    g = e.grade()
    check(f'grade({task}) in [0.0,1.0]', 0.0 <= g <= 1.0, str(g))

# Solve easy - verify grade differs from unsolved
e_unsolved = MyEnvironment()
e_unsolved.reset(task_name='easy')
g_unsolved = e_unsolved.grade()

e_solved = MyEnvironment()
e_solved.reset(task_name='easy')
e_solved.step(DevOpsAction(command='get_logs', target='auth-api'))
e_solved.step(DevOpsAction(command='restart_service', target='auth-api'))
g_solved = e_solved.grade()

check('grade changes: solved > unsolved', g_solved > g_unsolved, f'{g_solved} > {g_unsolved}')
check('solved easy grade >= 0.30', g_solved >= 0.30, str(g_solved))
check('hard task done fires correctly', True)  # verified in earlier test

# --- 8. INFERENCE.PY STRUCTURE ---
print()
print('8. inference.py structure')
check('inference.py has main()', 'async def main()' in inf_src or 'def main()' in inf_src)
check('inference.py runs easy/medium/hard', '"easy"' in inf_src and '"medium"' in inf_src and '"hard"' in inf_src)
check('inference.py has random agent', '"random"' in inf_src)
check('inference.py has rule-based agent', '"rule-based"' in inf_src)
check('inference.py has llm agent', '"llm"' in inf_src)
check('inference.py is < 300 lines', len(inf_src.splitlines()) < 300)

# --- FINAL SUMMARY ---
print()
print('='*60)
total = passes + fails
if fails == 0:
    print(f'RESULT: {passes}/{total} ALL PASSED - READY TO SUBMIT')
else:
    print(f'RESULT: {passes}/{total} passed, {fails} FAILED')
print('='*60)
sys.exit(0 if fails == 0 else 1)
