#!/usr/bin/env python3
import os
import requests

api_key = os.getenv("OPENAI_API_KEY", "")
base_url = os.getenv("OPENAI_BASE_URL", "")

print(f"API Key length: {len(api_key)}")
print(f"Base URL: {base_url}")

# Test direct API call
try:
    r = requests.post(
        f"{base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer ***
            "Content-Type": "application/json"
        },
        json={
            "model": "qwen3.7-plus",
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": 10
        },
        timeout=30
    )
    print(f"Status: {r.status_code}")
    if r.status_code == 200:
        print("SUCCESS: API call works!")
    else:
        print(f"Error: {r.text[:200]}")
except Exception as e:
    print(f"Exception: {type(e).__name__}: {str(e)[:200]}")
