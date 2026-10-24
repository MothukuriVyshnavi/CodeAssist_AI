import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.join(
    os.environ["USERPROFILE"],
    "OneDrive",
    "Desktop",
    "CodeAssist_AI",
)
PYTHON = os.path.join(PROJECT, ".venv", "Scripts", "python.exe")
ADAPTER = os.path.join(ROOT, "codeassist_adapter.py")

request = {
    "command": "Find errors in this Python code",
    "code": "def add(a, b)\n    return a + b\n",
}

try:
    completed = subprocess.run(
        [PYTHON, ADAPTER],
        input=json.dumps(request),
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
    )

    if completed.returncode != 0:
        print("FAIL: Adapter process returned a non-zero exit code.")
        print(completed.stderr)
        print(completed.stdout)
        sys.exit(1)

    result = json.loads(completed.stdout)

    if not result.get("ok"):
        print("FAIL: Adapter reported an error.")
        print(result.get("error", "Unknown error"))
        sys.exit(1)

    output = result.get("result", "")
    checks = {
        "orchestrator returned analysis": "ERROR DETECTION AGENT" in output,
        "syntax error was identified": "Syntax error" in output,
        "correction agent was invoked": "CODE CORRECTION AGENT" in output,
        "corrected code was proposed": "def add(a, b):" in output,
    }

    for description, passed in checks.items():
        print(f'{"PASS" if passed else "FAIL"}: {description}')

    passed_count = sum(checks.values())
    print(f"\nRESULT: {passed_count}/{len(checks)} checks passed")
    sys.exit(0 if all(checks.values()) else 1)

except subprocess.TimeoutExpired:
    print("FAIL: Adapter evaluation timed out.")
    sys.exit(1)
except (OSError, json.JSONDecodeError) as error:
    print(f"FAIL: Could not evaluate adapter: {error}")
    sys.exit(1)
