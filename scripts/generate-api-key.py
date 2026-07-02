import requests

resp = requests.post('http://localhost:8000/keys', json={'name': 'csv-editor'})
resp.raise_for_status()
key = resp.json()['api_key']
print(f"Add this to .env:\nOPENRAG_API_KEY={key}")