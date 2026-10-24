import json
import os
import sys
import traceback

CODEASSIST_ROOT = os.path.join(
    os.environ["USERPROFILE"],
    "OneDrive",
    "Desktop",
    "CodeAssist_AI",
)

sys.path.insert(0, CODEASSIST_ROOT)
os.chdir(CODEASSIST_ROOT)

from server.orchestrator import process_command


def main():
    request = json.load(sys.stdin)
    command = str(request.get("command", "")).strip()
    code = str(request.get("code", ""))

    if not command:
        print(json.dumps({
            "ok": False,
            "error": "A non-empty command is required.",
        }))
        return 2

    try:
        result = process_command(command, code)
        print(json.dumps({
            "ok": True,
            "result": result,
        }))
        return 0
    except Exception as error:
        print(json.dumps({
            "ok": False,
            "error": str(error),
            "traceback": traceback.format_exc(),
        }))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
