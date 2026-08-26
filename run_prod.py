#!/usr/bin/env python3
"""
DeepBrain production-quality server with gunicorn.

License: BSL 1.1 (see LICENSE in this directory)
CertainLogic <anton@certainlogic.ai> — (c) 2026

Run:
    python3 deepbrain/run_prod.py
    # or directly:
    gunicorn -w 4 -b 127.0.0.1:8081 'deepbrain.server:app'
"""

import os
import sys
import subprocess

WORKSPACE = os.path.expanduser("~/.openclaw/workspace")
os.chdir(WORKSPACE)

# Ensure gunicorn is installed
try:
    import gunicorn
except ImportError:
    print("Installing gunicorn...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "gunicorn", "-q"])

# Kill any existing processes on our ports
for port in ["8080", "8081"]:
    subprocess.run(
        ["bash", "-c", f"fuser -k {port}/tcp 2>/dev/null || true"],
        capture_output=True,
    )

print("Starting DeepBrain production stack...")
print("=" * 60)

# Start timechain API
print("\n[1/2] Starting timechain API on :8080...")
tc_proc = subprocess.Popen(
    [sys.executable, "scripts/timechain_api.py",
     "--port", "8080",
     "--root", os.path.join(WORKSPACE, "data/coder-executor-timechain")],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
)

# Start DeepBrain server with gunicorn
print("[2/2] Starting DeepBrain on :8081 (gunicorn)...")
import time
time.sleep(2)  # Let timechain start

# Use gunicorn for production
db_cmd = [
    "gunicorn",
    "-w", "2",  # 2 workers for CPU-bound
    "-b", "127.0.0.1:8081",
    "--timeout", "120",
    "--keep-alive", "30",
    "--access-logfile", "deepbrain/access.log",
    "--error-logfile", "deepbrain/error.log",
    "deepbrain.server:app",
]

db_proc = subprocess.Popen(
    db_cmd,
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
)

time.sleep(2)

print("\n" + "=" * 60)
print("DeepBrain production stack running:")
print("  Timechain: http://0.0.0.0:8080")
print("  DeepBrain: http://127.0.0.1:8081")
print("  Logs: deepbrain/access.log, deepbrain/error.log")
print("=" * 60)

# Monitor both processes
try:
    while True:
        tc_ret = tc_proc.poll()
        db_ret = db_proc.poll()
        if tc_ret is not None:
            print(f"❌ Timechain API exited with code {tc_ret}")
            break
        if db_ret is not None:
            print(f"❌ DeepBrain exited with code {db_ret}")
            break
        time.sleep(10)
except KeyboardInterrupt:
    print("\nShutting down...")
    tc_proc.terminate()
    db_proc.terminate()
    print("Done.")