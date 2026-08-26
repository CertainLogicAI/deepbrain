#!/bin/bash
# DeepBrain quickstart — start everything with one command.
# License: BSL 1.1 (see LICENSE in this directory)
# CertainLogic <anton@certainlogic.ai> — (c) 2026
# Usage:
#   bash deepbrain/start.sh              # start both services
#   bash deepbrain/start.sh --restart    # restart
#   bash deepbrain/start.sh --stop       # stop

cd /data/.openclaw/workspace
mkdir -p deepbrain/logs

case "${1:-}" in
  --stop)
    echo "Stopping DeepBrain..."
    pkill -f "timechain_api" 2>/dev/null || true
    pkill -f "gunicorn.*8081" 2>/dev/null || true
    pkill -f "deepbrain/server" 2>/dev/null || true
    echo "Stopped."
    exit 0
    ;;
  --restart)
    bash "$0" --stop
    sleep 2
    exec bash "$0"
    ;;
esac

echo "=== DeepBrain Startup ==="

# Kill old processes
pkill -f "timechain_api" 2>/dev/null || true
pkill -f "gunicorn.*8081" 2>/dev/null || true
sleep 1

# Start timechain API
echo "[1/3] Starting Timechain API on :8080..."
nohup python3 scripts/timechain_api.py --port 8080 \
  --root /data/.openclaw/workspace/data/coder-executor-timechain \
  > deepbrain/logs/timechain.log 2>&1 &
TC_PID=$!
echo "  PID: $TC_PID"
sleep 3

# Check it's up
if curl -sf http://127.0.0.1:8080/health > /dev/null 2>&1; then
  echo "  ✅ Timechain API is live"
else
  echo "  ⚠️  Timechain API may still be loading..."
fi

# Start DeepBrain server
echo "[2/3] Starting DeepBrain on :8081..."

# Check if gunicorn is installed
if ! command -v gunicorn &> /dev/null; then
  echo "  Installing gunicorn..."
  pip3 install gunicorn -q
fi

nohup gunicorn -w 2 -b 127.0.0.1:8081 --timeout 120 \
  --keep-alive 30 \
  --access-logfile deepbrain/logs/access.log \
  --error-logfile deepbrain/logs/error.log \
  deepbrain.server:app \
  > deepbrain/logs/server.log 2>&1 &
DB_PID=$!
echo "  PID: $DB_PID"
sleep 2

# Check it's up
if curl -sf http://127.0.0.1:8081/api/health > /dev/null 2>&1; then
  echo "  ✅ DeepBrain is live"
else
  echo "  ⚠️  DeepBrain may still be loading..."
fi

echo ""
echo "[3/3] Dependencies:"
curl -s http://127.0.0.1:8081/api/health 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "  (health check pending)"

echo ""
echo "=== Ready ==="
echo "  DeepBrain:    http://127.0.0.1:8081"
echo "  Timechain:    http://0.0.0.0:8080"
echo "  Logs:         deepbrain/logs/"
exit 0
