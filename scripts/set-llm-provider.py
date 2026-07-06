import os
import requests

from dotenv import load_dotenv

script_dir = os.path.dirname(__file__)
root_dir = os.path.dirname(script_dir)
load_dotenv(os.path.join(root_dir, ".env"))

openrag_api_key = os.getenv("OPENRAG_API_KEY", "")
llm_model = os.getenv("LLM_MODEL")
embedding_model = os.getenv("EMBEDDING_MODEL")

if not openrag_api_key:
    print("Error: OPENRAG_API_KEY is not set. Run scripts/generate-api-key.py first.")
    raise SystemExit(1)

# Let the OpenRAG backend's own settings endpoint wire Ollama into every
# Langflow flow (chat, ingest, url-ingest, nudges). It knows how to resolve
# provider-specific fields (e.g. Ollama's base URL) correctly; hand-patching
# the flow JSON ourselves missed those fields and got clobbered on restart.
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
print(f"Configured Ollama provider: llm={llm_model}, embedding={embedding_model}")