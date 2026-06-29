import os
import requests

script_dir = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(script_dir, 'system_prompt.txt')) as prompt_in:
    prompt = prompt_in.read()

port = os.environ.get('FRONTEND_PORT', '3000')
resp = requests.post(f'http://localhost:{port}/api/settings', json={'system_prompt': prompt})
resp.raise_for_status()
print(resp.json().get('message', resp.json()))
