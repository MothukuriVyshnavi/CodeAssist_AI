
from server.agents.code_correction_agent import correct_code

code = """def add(a, b)
    return a + b"""

errors = "Syntax error on line 1: expected ':'"

result = correct_code(code, errors)

print("ORIGINAL CODE:")
print(result["original_code"])

print("\nCORRECTION:")
print(result["correction"])