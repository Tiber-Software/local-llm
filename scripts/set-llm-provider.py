import os
import requests

from dotenv import load_dotenv

script_dir = os.path.dirname(__file__)
root_dir = os.path.dirname(script_dir)
load_dotenv(os.path.join(root_dir, ".env"))

langflow_port = os.getenv('LANGFLOW_PORT', '7860')
langflow_base = f'http://localhost:{langflow_port}'
langflow_user = os.getenv('LANGFLOW_SUPERUSER', 'admin')
langflow_pass = os.getenv('LANGFLOW_SUPERUSER_PASSWORD', '')

llm_model = os.getenv("LLM_MODEL")
ollama_endpoint = os.getenv("OLLAMA_ENDPOINT")

frontend_port = os.getenv("FRONTEND_PORT")
settings = requests.get(f'http://localhost:{frontend_port}/api/settings').json()
flow_id = settings.get('flow_id')

if not flow_id:
    print('Error: could not get flow_id from OpenRAG settings')

token_resp = requests.post(
    f"{langflow_base}/api/v1/login",
    data={"username": langflow_user, "password": langflow_pass},
    headers={'Content-Type': 'application/x-www-urlencoded'}
)
token_resp.raise_for_status()
token = token_resp.json()['access_token']
lf_headers = {'Authorization': f"Bearer {token}"}

flow_resp = requests.get(f"{langflow_base}/api/v1/flows/{flow_id}", headers=lf_headers)
flow_resp.raise_for_status()

ollama_model_value = [{
    'name': llm_model,
    'icon': 'Ollama',
    'category': 'Ollama',
    'provider': 'Ollama',
    'base_url': ollama_endpoint,
    'metadata': {
        'context_length': 128000,
        'model_class': 'ChatOllama',
        'model_name_param': 'model',
        'api_key_param': 'api_key',
        'max_tokens_field_name': 'max_tokens',
        'base_url_param': 'base_url'
    }
}]

updated = False
for node in flow.get('data', {}).get('nodes', []):
    if node.get('data', {}).get('type', '') == 'Agent':
        template = node['data']['node']['template']
        template['model']['value'] = ollama_model_value
        updated = True

if not updated:
    print("Warning: no Agent node found in flow")
else:
    patch_resp = requests.patch(
        f"{langflow_base}/api/v1/flows/{flow_id}",
        json=flow,
        headers=lf_headers
    )
    patch_resp.raise_for_status()
    print(f"Flow {flow_id} Agent node updated to Ollama/{llm_model}")