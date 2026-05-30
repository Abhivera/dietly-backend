#!/usr/bin/env bash
# Restart DynamoDB Local and the API (fresh in-memory tables).
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose down -v
docker compose up -d --build
echo "DynamoDB Local + API restarted. Tables are recreated when SCHEMA_AUTO_CREATE=true."
