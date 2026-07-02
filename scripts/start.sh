#!/bin/bash
set -e

[ -n "$1" ] && csv_file=$(realpath "$1") || csv_file=""

cd "$(dirname "$0")"

echo "Starting stack..."
docker compose -f ../docker/docker-compose.yml -f ../docker/docker-compose.gpu.yml --env-file ../.env up -d --build

echo "Waiting for backend..."
until curl -sf http://localhost:8000/health > /dev/null; do
    sleep 3
done

echo "Waiting for langflow..."
until curl -sf http://localhost:7860/health > /dev/null; do
    sleep 3
done

echo "Pulling models..."
./bootstrap-ollama.sh

echo "Apllying system prompt..."
python3 set-system-prompt.py

echo "Setting LLM provider..."
python3 set-llm-provider.py

echo "Checking api key..."
python3 generate-api-key.py

if [ -n "$csv_file" ]; then
    docker exec -it csv-editor python main.py "/app/csvs/$(basename "$csv_file")"
else
    docker exec -it csv-editor python main.py
fi