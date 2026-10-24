#!/bin/sh
# Production start (Render): apply migrations, then run the API. Docker Compose uses the
# Dockerfile CMD instead, with migrations in their own service.
set -e
alembic upgrade head
exec fastapi run app/main.py --host 0.0.0.0 --port "${PORT:-8000}"
