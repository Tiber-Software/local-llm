#!/bin/bash
set -e

cd "$(dirname "$0")"

docker compose -f ../docker/docker-compose.yml -f ../docker/docker-compose.gpu.yml --env-file ../.env down

./start.sh
