
from server.agents.error_detection_agent import detect_errors


def check_case(name, code, expected_category, unexpected_category=None):
    result = detect_errors(code)
    findings = result["findings"]

    expected = findings[expected_category]
    unexpected = findings.get(unexpected_category, []) if unexpected_category else []

    passed = bool(expected) and not unexpected

    print(f"\n--- {name}: {'PASS' if passed else 'FAIL'} ---")
    print("Language:", result["language"])
    print("Expected category:", expected_category, expected)
    if unexpected_category:
        print("Unexpected category:", unexpected_category, unexpected)

    return passed


tests = [
    (
        "Undefined variable",
        "print(price)",
        "undefined_names",
        "runtime_errors",
    ),
    (
        "Division by zero",
        "result = 10 / 0",
        "runtime_errors",
        None,
    ),
    (
        "Type error",
        'result = "5" + 2',
        "type_errors",
        None,
    ),
    (
        "Out-of-range index",
        "items = [1, 2]\nprint(items[5])",
        "runtime_errors",
        None,
    ),
    (
        "Missing colon",
        "def add(a, b)\n    return a + b",
        "syntax_errors",
        None,
    ),
]

results = [
    check_case(name, code, expected, unexpected)
    for name, code, expected, unexpected in tests
]

print(f"\nPassed: {sum(results)}/{len(results)}")
if not all(results):
    raise SystemExit(1)
