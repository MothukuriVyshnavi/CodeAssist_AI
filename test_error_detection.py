
from server.agents.error_detection_agent import detect_errors

code = """
def add(a, b)
    return a + b
"""

result = detect_errors(code)

print("Syntax error:", result["syntax_error"])
print("AI analysis:", result["analysis"])