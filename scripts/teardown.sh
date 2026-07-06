#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "Stopping docker containers and volumes..."
docker compose -f ../docker/docker-compose.yml -f ../docker/docker-compose.gpu.yml --env-file ../.env down -v

echo "Removing persistent data..."
rm -rf ../data/*
rm -rf ../config/*
rm -rf ../keys/*
rm -rf ../flows/runtime/*
rm -rf ../documents/*

echo "Clearing ingested file tracking..."
> ../documents/.ingested

echo "Copying inject document to documents dir..."
cp ../documents.example/* ../documents/

echo "Done."