#!/usr/bin/env bash
# Fresh Postgres with database "calovia" (no data preserved).
set -euo pipefail
cd "$(dirname "$0")/.."

if docker compose version &>/dev/null; then
  DC="docker compose"
elif command -v docker-compose &>/dev/null; then
  DC="docker-compose"
else
  echo "Install Docker Compose, then re-run this script." >&2
  exit 1
fi

echo "Stopping stack and removing volumes..."
$DC down -v

echo "Starting Postgres + API with empty calovia database..."
$DC up --build -d

echo "Done. API: http://localhost:8000  Docs: http://localhost:8000/docs"
