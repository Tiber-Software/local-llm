import copy
import os
import requests

from dotenv import load_dotenv

script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(script_dir)
load_dotenv(os.path.join(root_dir, ".env"))

openrag_api_key = os.getenv("OPENRAG_API_KEY", "")
llm_model = os.getenv("LLM_MODEL")
embedding_model = os.getenv("EMBEDDING_MODEL")

if not openrag_api_key:
    print("Error: OPENRAG_API_KEY is not set. Run scripts/generate-api-key.py first.")
    raise SystemExit(1)

# The OpenRAG backend's settings endpoint wires Ollama into config.yaml and
# handles fields like OLLAMA_BASE_URL correctly, so always call it first.
resp = requests.post(
    "http://localhost:8000/v1/settings",
    headers={"X-API-KEY": openrag_api_key, "Content-Type": "application/json"},
    json={
        "llm_provider": "ollama",
        "llm_model": llm_model,
        "embedding_provider": "ollama",
        "embedding_model": embedding_model,
    },
)
resp.raise_for_status()
print(f"Configured Ollama provider via OpenRAG settings: llm={llm_model}, embedding={embedding_model}")

langflow_port = os.getenv("LANGFLOW_PORT", "7860")
langflow_base = f"http://localhost:{langflow_port}"
langflow_user = os.getenv("LANGFLOW_SUPERUSER", "admin")
langflow_pass = os.getenv("LANGFLOW_SUPERUSER_PASSWORD", "")

token_resp = requests.post(
    f"{langflow_base}/api/v1/login",
    data={"username": langflow_user, "password": langflow_pass},
    headers={"Content-Type": "application/x-www-form-urlencoded"},
)
token_resp.raise_for_status()
lf_headers = {"Authorization": f"Bearer {token_resp.json()['access_token']}"}

flow_ids = {
    "chat": os.getenv("LANGFLOW_CHAT_FLOW_ID", ""),
    "ingest": os.getenv("LANGFLOW_INGEST_FLOW_ID", ""),
    "url ingest": os.getenv("LANGFLOW_URL_INGEST_FLOW_ID", ""),
    "nudges": os.getenv("NUDGES_FLOW_ID", ""),
}

model_by_type = {"language": llm_model, "embedding": embedding_model}

for flow_name, flow_id in flow_ids.items():
    if not flow_id:
        continue

    flow_resp = requests.get(f"{langflow_base}/api/v1/flows/{flow_id}", headers=lf_headers)
    flow_resp.raise_for_status()
    flow = flow_resp.json()

    updated_nodes = []
    for node in flow.get("data", {}).get("nodes", []):
        template = node.get("data", {}).get("node", {}).get("template", {})
        model_field = template.get("model")
        if not model_field or model_field.get("type") != "model":
            continue

        target_model = model_by_type.get(model_field.get("model_type"))
        if not target_model:
            continue

        ollama_option = next(
            (o for o in model_field.get("options", []) if o.get("provider") == "Ollama"),
            None,
        )
        if not ollama_option:
            print(f"Warning: no Ollama option found for {node['data']['id']} in {flow_name} flow; skipping")
            continue

        new_value = copy.deepcopy(ollama_option)
        new_value["name"] = target_model
        model_field["value"] = [new_value]
        updated_nodes.append(node["data"]["id"])

    if not updated_nodes:
        print(f"No model fields found to update in {flow_name} flow")
        continue

    patch_resp = requests.patch(
        f"{langflow_base}/api/v1/flows/{flow_id}",
        json=flow,
        headers=lf_headers,
    )
    patch_resp.raise_for_status()
    print(f"Set Ollama on {flow_name} flow nodes: {', '.join(updated_nodes)}")