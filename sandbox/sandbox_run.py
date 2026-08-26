#!/usr/bin/env python3
"""Sandbox runner — receives code via stdin, executes, returns JSON result."""
# License: BSL 1.1 (see LICENSE in this directory)
# CertainLogic <anton@certainlogic.ai> — (c) 2026
import json
import sys
import os
import traceback

def main():
    try:
        data = json.loads(sys.stdin.read())
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}", "exit_code": -1, "stdout": "", "stderr": ""}))
        sys.exit(1)

    code = data.get("code", "")
    language = data.get("language", "python")

    if not code:
        print(json.dumps({"error": "No code provided", "exit_code": -1, "stdout": "", "stderr": ""}))
        sys.exit(1)

    result = {"stdout": "", "stderr": "", "exit_code": -1, "error": None}

    if language in ("python", "py"):
        import subprocess
        wrapped = f"""import sys, traceback
try:
{chr(10).join('    ' + line for line in code.split(chr(10)))}
except Exception:
    traceback.print_exc()
    sys.exit(1)
"""
        proc = subprocess.run(
            ["python3", "-c", wrapped],
            capture_output=True, text=True, timeout=30,
        )
        result["stdout"] = proc.stdout
        result["stderr"] = proc.stderr
        result["exit_code"] = proc.returncode
    elif language in ("sh", "bash"):
        import subprocess
        proc = subprocess.run(
            ["bash", "-c", code],
            capture_output=True, text=True, timeout=30,
        )
        result["stdout"] = proc.stdout
        result["stderr"] = proc.stderr
        result["exit_code"] = proc.returncode
    elif language in ("js", "javascript"):
        import subprocess
        proc = subprocess.run(
            ["node", "-e", code],
            capture_output=True, text=True, timeout=30,
        )
        result["stdout"] = proc.stdout
        result["stderr"] = proc.stderr
        result["exit_code"] = proc.returncode
    else:
        result["error"] = f"Unsupported language: {language}"

    # Limit output size
    MAX_OUTPUT = 500000
    result["stdout"] = result.get("stdout", "")[:MAX_OUTPUT]
    result["stderr"] = result.get("stderr", "")[:MAX_OUTPUT]

    print(json.dumps(result))


if __name__ == "__main__":
    main()