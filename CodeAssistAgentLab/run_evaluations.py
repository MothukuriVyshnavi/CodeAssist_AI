import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON = Path(
    r"C:\Users\jahna\OneDrive\Desktop\CodeAssist_AI\.venv\Scripts\python.exe"
)

TESTS = [
    ("individual_agents", ROOT / "codeassist_agent_eval.py"),
    ("adapter_integration", ROOT / "codeassist_adapter_eval.py"),
]

results = []

for name, script in TESTS:
    print(f"\n===== {name} =====", flush=True)

    try:
        process = subprocess.run(
            [str(PYTHON), str(script)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=180,
        )
        stdout = process.stdout
        stderr = process.stderr
        exit_code = process.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = (exc.stderr or "") + "\nTimed out after 180 seconds."
        exit_code = 124

    if isinstance(stdout, bytes):
        stdout = stdout.decode(errors="replace")
    if isinstance(stderr, bytes):
        stderr = stderr.decode(errors="replace")

    print(stdout, end="" if stdout.endswith("\n") or not stdout else "\n")
    if stderr:
        print(stderr, file=sys.stderr)

    passed = exit_code == 0
    print(f"Exit code: {exit_code}")
    print(f"Status: {'PASS' if passed else 'FAIL'}")

    results.append({
        "name": name,
        "script": str(script),
        "exit_code": exit_code,
        "passed": passed,
        "stdout": stdout,
        "stderr": stderr,
    })

report = {
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "passed": sum(item["passed"] for item in results),
    "total": len(results),
    "success": all(item["passed"] for item in results),
    "tests": results,
}

report_dir = ROOT / ".harness" / "runs"
report_dir.mkdir(parents=True, exist_ok=True)
report_path = report_dir / "evaluation-report.json"
report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

print(f"\nRESULT: {report['passed']}/{report['total']} evaluations passed")
print(f"Report: {report_path}")
sys.exit(0 if report["success"] else 1)
