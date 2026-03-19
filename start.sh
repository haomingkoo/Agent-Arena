#!/usr/bin/env bash
set -e

# Build frontend if not already built
if [ ! -d "frontend/dist" ]; then
  echo "Building frontend..."
  cd frontend && npm ci && npm run build && cd ..
fi

# Init database
python -c "from store.db import init_db; init_db()"

# Start API server
exec uvicorn api.app:app --host 0.0.0.0 --port "${PORT:-8000}"
