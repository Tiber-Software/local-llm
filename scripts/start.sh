#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "Starting stack..."
docker compose -f ../docker/docker-compose.yml -f ../docker/docker-compose.gpu.yml --env-file ../.env up -d --build --wait --wait-timeout 300

echo "Pulling models..."
./bootstrap-ollama.sh

echo "Generating API key..."
python3 generate-api-key.py

echo "Restarting stack with api key..."
docker compose -f ../docker/docker-compose.yml -f ../docker/docker-compose.gpu.yml --env-file ../.env up -d --build --wait --wait-timeout 300

echo "Running onboarding..."
python3 onboard.py

echo "Apllying system prompt..."
python3 set-system-prompt.py

echo "Setting LLM provider..."
python3 set-llm-provider.py

echo "Setting max tokens..."
python3 set-max-tokens.py
