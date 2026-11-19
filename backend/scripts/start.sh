#!/bin/sh
set -e

alembic upgrade head
python -m app.scripts.create_super_admin
exec uvicorn app.main:app --host 0.0.0.0 --port "${APP_PORT:-8000}" --proxy-headers
