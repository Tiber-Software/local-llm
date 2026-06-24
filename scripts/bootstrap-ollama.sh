#!/bin/bash
set -e

echo "Waiting for Ollama..."
until curl -s http://localhost:11434/api/tags; do
    sleep 2
done

echo "Pulling models..."
docker exec ollama ollama pull llama3.2
docker exec ollama ollama pull embeddinggemma

echo "Done."