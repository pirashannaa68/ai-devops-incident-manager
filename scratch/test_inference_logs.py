import asyncio
import os
import json
from openai import OpenAI

# Mock env vars
os.environ["API_BASE_URL"] = "http://localhost:8000"
os.environ["MODEL_NAME"] = "test-model"
os.environ["HF_TOKEN"] = "test-token"

from inference import run_scenario

async def test_logs():
    # We use a dummy client since we'll only run 'random' or 'rule-based' which don't use it
    client = OpenAI(api_key="sk-test", base_url="http://localhost:8000")
    print("Testing 'random' scenario logs for 'easy' task...")
    await run_scenario(client, "easy", "random")

if __name__ == "__main__":
    asyncio.run(test_logs())
