#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "Starting stack..."
docker compose -f ../docker/docker-compose.yml -f ../docker/docker-compose.gpu.yml --env-file ../.env up -d --build

echo "Waiting 90 seconds for services to warm up..."
sleep 90

echo "Pulling models..."
./bootstrap-ollama.sh

if [ -z "$(ls -A ../keys 2>/dev/null)" ]; then
    echo "Initital start; generating api key..."
    python3 generate-api-key.py
else
    echo "Subsequent start; using old api key..."
fi

echo "Running onboarding..."
python3 onboard.py

echo "Apllying system prompt..."
python3 set-system-prompt.py

echo "Setting LLM provider..."
python3 set-llm-provider.py

docker exec -it csv-editor python main.py