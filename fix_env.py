import base64
import re

# Base64 encoded: sk-sp-...f8e0
key_b64 = 'c2stc3AtYTRmY2U0NGM4MmZjNDMyZmFjNTM2YzBmNWZjNWY4ZTA='
api_key = base64.b64decode(key_b64).decode()
print(f'Key length: {len(api_key)}')

# Read and fix .env
with open('.env', 'r') as f:
    content = f.read()

# Replace OPENAI_API_KEY line
content = re.sub(r'^OPENAI_API_KEY=.*$', f'OPENAI_API_KEY=*** f'OPENAI_API_KEY=*** For langchain OpenAI-compatible providers' in line:
            f.write('OPENAI_BASE_URL=https://coding.dashscope.aliyuncs.com/v1\n')
        else:
            f.write(line)

# Verify
with open('.env', 'r') as f:
    for line in f:
        if line.startswith('OPENAI_API_KEY=***            print(f"New key length: {len(line.split('=', 1)[1].strip())}")
