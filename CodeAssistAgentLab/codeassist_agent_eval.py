import ast
import os
import sys

CODEASSIST_ROOT = os.path.join(
    os.environ["USERPROFILE"], "OneDrive", "Desktop", "CodeAssist_AI"
)
sys.path.insert(0, CODEASSIST_ROOT)
os.chdir(CODEASSIST_ROOT)

from server.agents.command_agent import understand_command
from server.agents.error_detection_agent import detect_errors
from server.agents.code_correction_agent import correct_code


def check(condition, message):
    print(f'{"PASS" if condition else "FAIL"}: {message}')
    return bool(condition)


results = []

# Agent 1: command understanding
command_result = understand_command("Explain a Python function")
results.append(check(
    command_result.get("task") == "explain_code",
    "Command agent classifies an explanation request",
))

# Agent 2: syntax error detection
broken_code = "def add(a, b)\n    return a + b\n"
detection = detect_errors(broken_code)
results.append(check(
    detection.get("has_syntax_error") is True
    and bool(detection.get("syntax_error")),
    "Error agent detects the missing colon",
))
# Agent 2: valid Python should not be flagged
valid_code = "def add(a, b):\n    return a + b\n"
valid_detection = detect_errors(valid_code)
results.append(check(
    valid_detection.get("has_syntax_error") is False
    and valid_detection.get("syntax_error") is None,
    "Error agent accepts valid Python syntax",
))
# Agent 3: correction
correction_result = correct_code(
    broken_code,
    "Syntax error: missing colon after the function definition",
)
correction_text = correction_result.get("correction", "")

corrected_code = ""
if "CORRECTED_CODE:" in correction_text:
    section = correction_text.split("CORRECTED_CODE:", 1)[1]
    parts = section.split("```")
    if len(parts) >= 3:
        corrected_code = parts[1].strip()
        if corrected_code.startswith("python"):
            corrected_code = corrected_code[len("python"):].strip()

syntax_valid = False
if corrected_code:
    try:
        ast.parse(corrected_code)
        syntax_valid = True
    except SyntaxError:
        pass

results.append(check(
    syntax_valid,
    "Correction agent returns syntactically valid Python",
))

passed = sum(results)
print(f"\nRESULT: {passed}/{len(results)} checks passed")
sys.exit(0 if all(results) else 1)
