import requests
import os

from dotenv import load_dotenv

script_dir = os.path.dirname(__file__)
root_dir = os.path.dirname(script_dir)
load_dotenv(os.path.join(root_dir, ".env"))

if not os.getenv("OPENRAG_API_KEY"):
    resp = requests.post('http://localhost:8000/keys', json={'name': 'csv-editor'})
    resp.raise_for_status()
    key = resp.json()['api_key']

    print(f"Add this to .env:\nOPENRAG_API_KEY={key}")
else:
    print("OPENRAG_API_KEY variable already set!")