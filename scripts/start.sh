#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "Starting stack..."
docker compose -f ../docker/docker-compose.yml -f ../docker/docker-compose.gpu.yml --env-file ../.env up -d --build

echo "Waiting for frontend..."
until curl -sf "http://localhost:${FRONTEND_PORT:-3000}/api/settings" > /dev/null 2>&1; do
    sleep 3
done

echo "Pulling models..."
./bootstrap-ollama.sh

echo "Apllying system prompt..."
python3 set-system-prompt.py

echo "Setting LLM provider..."
python3 set-llm-provider.py

echo "Done."