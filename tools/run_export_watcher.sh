#!/usr/bin/env bash
cd "$(dirname "$0")"
# Run the export_to_obsidian watcher in background with nohup
PYTHON=$(which python3 || echo python3)
nohup "$PYTHON" export_to_obsidian.py >> /Users/minime/research_project/brainstorm/LOGS/export_stdout.log 2>&1 &
echo $! > /Users/minime/research_project/brainstorm/LOGS/export_watcher.pid
