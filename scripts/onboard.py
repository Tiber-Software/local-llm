import os
import requests

from dotenv import load_dotenv

script_dir = os.path.dirname(__file__)
root_dir = os.path.dirname(script_dir)
load_dotenv(os.path.join(root_dir, ".env"))

llm_model = os.getenv("LLM_MODEL")
embedding_model = os.getenv("EMBEDDING_MODEL")

resp = requests.post(
    "http://localhost:8000/onboarding",
    headers={"Content-Type": "application/json"},
    json={
        "llm_provider": "ollama",
        "llm_model": llm_model,
        "embedding_provider": "ollama",
        "embedding_mode": embedding_model
    }
)

resp.raise_for_status()
print(resp.json().get("message", resp.json()))