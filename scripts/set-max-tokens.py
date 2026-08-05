import os
import requests

from dotenv import load_dotenv

script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(script_dir)

load_dotenv(os.path.join(root_dir, '.env'))

max_tokens = os.getenv("MAX_TOKENS", "").strip()

# Skip if not set
if not max_tokens:
    print("MAX_TOKENS not set in .env; skipping")
    exit(0)

# Convert to int
try:
    max_tokens_value = int(max_tokens)
except ValueError:
    print(f"Error: MAX_TOKENS must be an integer, got '{max_tokens}'")
    raise SystemExit(1)

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

flow_id = os.getenv("LANGFLOW_CHAT_FLOW_ID", "")

flow_resp = requests.get(f'{langflow_base}/api/v1/flows/{flow_id}', headers=lf_headers)
flow_resp.raise_for_status()
flow = flow_resp.json()

# Update max_tokens in Agent node
updated = False
for node in flow.get('data', {}).get('nodes', []):
    template = node.get('data', {}).get('node', {}).get('template', {})
    if 'max_tokens' in template:
        template['max_tokens']['value'] = max_tokens_value
        updated = True

if not updated:
    print('Warning: no Agent node with max_tokens found in flow; Langflow not updated')
else:
    patch_resp = requests.patch(
        f'{langflow_base}/api/v1/flows/{flow_id}',
        json=flow,
        headers=lf_headers,
    )
    patch_resp.raise_for_status()
    print(f'Langflow flow {flow_id} Agent node max_tokens updated to {max_tokens_value}')
