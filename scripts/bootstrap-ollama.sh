#!/bin/bash
set -e

llm=$1
embeddingmodel=$2

if [ -z "$llm" ] || [ -z "$embeddingmodel" ]; then
    echo "Usage: $0 <llm_model> <embedding_model>"
    echo "Example: $0 llama3.2 embeddinggemma"
    exit 1
fi

echo "Waiting for Ollama..."
until curl -s http://localhost:11434/api/tags > /dev/null 2>&1; do
    sleep 2
done

echo "Pulling models..."
docker exec ollama ollama pull $llm
docker exec ollama ollama pull $embeddingmodel

echo "Done."