#!/bin/bash
# Brainstorm — start the web app
BRAINSTORM_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV="$BRAINSTORM_DIR/venv"

if [ ! -d "$VENV" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV"
    "$VENV/bin/pip" install -q -r "$BRAINSTORM_DIR/requirements.txt"
fi

mkdir -p "$BRAINSTORM_DIR/sessions"

source "$VENV/bin/activate"
cd "$BRAINSTORM_DIR"

PORT="${BRAINSTORM_PORT:-8765}"
echo "Starting Brainstorm at http://localhost:$PORT"
uvicorn src.main:app --host 0.0.0.0 --port "$PORT" --reload
