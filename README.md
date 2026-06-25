# Requirements
- Docker Desktop
- Python
- If on windows, WSL

# Setup
1. Setup .env
  - Copy .env.example and rename to .env
  - Set the following required variables (follow the steps in the file):
    - LANGFLOW_SECRET_KEY
    - OPENRAG_ENCRYPTION_KEY
    - OPENSEARCH_PASSWORD
    - LLM_MODEL (can be any llm ollama model. I suggest llama3.2 for a small model)
    - EMBEDDING_MODEL (can be any embedding ollama model. I suggest embeddinggemma)
    - LANGFLOW_SUPERUSER_PASSWORD (set a strong password)

2. Go to ```docker/``` and run ```docker compose --env-file ../.env up```

2. If running for the firs ttime, run ```scripts/bootstrap-ollama.sh <LLM_MODEL> <EMBEDDING_MODEL>```
  - Note that LLM_MODEL and EMBEDDING_MODEL should match the model names from step 1

3. Go to ```localhost:3000``` and follow steps


# Teardown
- For a soft reset, run ```docker compose down``` from ```docker/```
    - This will maintain scripts and settings
- To delete the volumes, run ```docker compose down -v``` from ```docker/```
- To perform a hard reset, run ```scripts/teardown.sh```
    - Note that this will remove all chats, documents, etc.