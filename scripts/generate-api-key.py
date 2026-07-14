import os

import requests

script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(script_dir)
env_path = os.path.join(root_dir, '.env')

resp = requests.post('http://localhost:8000/keys', json={'name': 'csv-editor'})
resp.raise_for_status()
key = resp.json()['api_key']

with open(env_path) as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if line.startswith('OPENRAG_API_KEY='):
        lines[i] = f'OPENRAG_API_KEY={key}\n'
        break
else:
    lines.append(f'OPENRAG_API_KEY={key}\n')

with open(env_path, 'w') as f:
    f.writelines(lines)

print(f"Generated new OPENRAG_API_KEY and saved to {env_path}")