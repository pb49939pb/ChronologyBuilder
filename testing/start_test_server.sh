#!/bin/sh
# Starts a dedicated LawFirmAgent instance on port 5051, isolated from the normal port 5050 a
# person would actually use. Automated tests hit this one instead, so a test run's session-cleanup
# behavior (each /analyze deletes the previous session's files) never disrupts someone's live app.
set -e

PORT=5051
PID=$(lsof -tiTCP:$PORT 2>/dev/null || true)
if [ -n "$PID" ]; then
  kill "$PID"
  sleep 1
fi

WEBAPP_DIR="$(cd "$(dirname "$0")/../webapp" && pwd)"
LOG_FILE="/tmp/lawfirmagent_test_server.log"

LAWFIRMAGENT_PORT=$PORT nohup "$WEBAPP_DIR/.venv/bin/python" "$WEBAPP_DIR/app.py" > "$LOG_FILE" 2>&1 &
disown

sleep 2
if curl -s -o /dev/null -w "" "http://127.0.0.1:$PORT/"; then
  echo "Test server running on http://127.0.0.1:$PORT (log: $LOG_FILE)"
else
  echo "Test server failed to start — check $LOG_FILE"
  exit 1
fi
