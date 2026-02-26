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

# Kill any existing Brainstorm process on this port
OLD_PID=$(lsof -ti tcp:"$PORT" 2>/dev/null)
if [ -n "$OLD_PID" ]; then
    echo "Port $PORT is occupied (PID $OLD_PID). Killing old process..."
    kill $OLD_PID 2>/dev/null
    sleep 0.5
    # Force kill if still alive
    kill -0 $OLD_PID 2>/dev/null && kill -9 $OLD_PID 2>/dev/null
fi

echo "Starting Brainstorm at http://localhost:$PORT"
uvicorn src.main:app --host 0.0.0.0 --port "$PORT" --reload
