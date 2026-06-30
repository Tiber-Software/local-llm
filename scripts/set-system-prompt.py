import os
import requests

from dotenv import load_dotenv

script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(script_dir)

load_dotenv(os.path.join(root_dir, '.env'))

with open(os.path.join(script_dir, 'system_prompt.txt')) as prompt_in:
    prompt = prompt_in.read()

port = os.getenv('FRONTEND_PORT', '3000')
base = f'http://localhost:{port}'

# Save to OpenRAG settings
resp = requests.post(f'{base}/api/settings', json={'system_prompt': prompt})
resp.raise_for_status()
print(resp.json().get('message', resp.json()))

# Save to Langflow
langflow_port = os.getenv('LANGFLOW_PORT', '7860')
langflow_base = f'http://localhost:{langflow_port}'
langflow_user = os.getenv('LANGFLOW_SUPERUSER', 'admin')
langflow_pass = os.getenv('LANGFLOW_SUPERUSER_PASSWORD', '')

token_resp = requests.post(
    f'{langflow_base}/api/v1/login',
    data={'username': langflow_user, 'password': langflow_pass},
    headers={'Content-Type': 'application/x-www-form-urlencoded'},
)
token_resp.raise_for_status()
token = token_resp.json()['access_token']
lf_headers = {'Authorization': f'Bearer {token}'}

# Fetch current chat flow ID from OpenRAG settings
settings = requests.get(f'{base}/api/settings').json()
flow_id = settings.get('flow_id')

if not flow_id:
    print('Warning: could not determine chat flow ID from settings; skipping Langflow patch')
else:
    flow_resp = requests.get(f'{langflow_base}/api/v1/flows/{flow_id}', headers=lf_headers)
    flow_resp.raise_for_status()
    flow = flow_resp.json()

    # Update prompts
    updated = False
    for node in flow.get('data', {}).get('nodes', []):
        template = node.get('data', {}).get('node', {}).get('template', {})
        if 'system_prompt' in template:
            template['system_prompt']['value'] = prompt
            updated = True

    if not updated:
        print('Warning: no Agent node with system_prompt found in flow; Langflow not updated')
    else:
        patch_resp = requests.patch(
            f'{langflow_base}/api/v1/flows/{flow_id}',
            json=flow,
            headers=lf_headers,
        )
        patch_resp.raise_for_status()
        print(f'Langflow flow {flow_id} Agent node system_prompt updated')
        
