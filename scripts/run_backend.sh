#!/usr/bin/env bash
set -e

cd /workspaces/Project-Saas
source .venv/bin/activate
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
