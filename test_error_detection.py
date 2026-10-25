from server.agents.error_detection_agent import detect_errors

tests = {
    "Syntax error": "def add(a, b)\n    return a + b",
    "Undefined variable": "print(price)",
    "Division by zero": "result = 10 / 0",
    "Type error": 'result = "5" + 2',
    "Index error": "items = [1, 2]\nprint(items[5])",
    "Logical bug": "def maximum(a, b):\n    return a if a < b else b",
    "Valid code": "def add(a, b):\n    return a + b",
}

for name, code in tests.items():
    result = detect_errors(code)
    print(f"\n--- {name} ---")
    print("Has errors:", result.get("has_errors"))
    print("Findings:", result.get("findings"))
    print("Analysis:", result.get("analysis"))