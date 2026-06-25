#!/bin/bash

echo "Stopping docker containers and volumes..."
docker compose -f ../docker/docker-compose.yml down -v

echo "Removing persistent data..."
rm -rf ../data/*
rm -rf ../config/*
rm -rf ../keys/*
rm -rf ../flows/runtime/*
rm -rf ../documents/*

echo "Done."