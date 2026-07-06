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
    - OPENRAG_API_KEY (run ```python scripts/generate-api-key.py```)

2. Copy documents.example directory and rename to documents
  - These are example injections documents that OpenRAG injests at startup

3. Run ```scripts/start.sh```
  - This script performs the following tasks:
    1. Runs ```docker compose --env-file ../.env up```, starting the containers
    2. Runs ```scripts/bootstrap-ollama.sh```, pulling llm and embedding models
    3. Runs ```python scripts/onboard.py```, setting llm and embedding settings
    4. Runs ```python scripts/set-system-prompt.sh```, setting the system prompt
    5. Runs ```python scripts/set-llm-provider.sh```, setting the llm provider to ollama
    6. Runs ```docker exec -it csv-editor python main.py``` starting the application

# Teardown
- For a soft reset, run ```docker compose down``` from ```docker/```
    - This will maintain scripts, settings, and models
- To delete the models installed, run ```docker compose down -v``` from ```docker/```
- To perform a hard reset, run ```scripts/teardown.sh```
    - Note that this will remove all chats, documents, etc.


# Setting System Prompt
To set the system prompt, edit ```scripts/system_prompt.txt``` and then run ```python scripts/set-system-prompt.sh```