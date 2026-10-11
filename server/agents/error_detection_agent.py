
import ast

from server.services.llm_service import ask_ai


def detect_errors(code: str) -> dict:
    """Check Python syntax and analyze possible code errors."""

    syntax_error = None

    try:
        ast.parse(code)
    except SyntaxError as error:
        syntax_error = (
            f"Syntax error on line {error.lineno}: {error.msg}"
        )
        
    prompt = f"""
You are the Error Detection Agent in CodeAssist AI.

Analyze the Python code below for possible errors.

IMPORTANT RULES:
1. A syntax error reported by Python must never be described as
   correct code.
2. Focus on actual syntax errors, runtime risks, and logical bugs.
3. Do not invent problems that are not supported by the code.
4. Do not correct or rewrite the code.
5. If a syntax error exists, explain it clearly.
6. If the code appears correct, say that no obvious errors were found.
   Do not claim that the code is guaranteed to be correct.

Python syntax check result:
{syntax_error or "No Python syntax error detected."}

Code:
```python
{code}
```

Return a concise analysis.
"""

    analysis = ask_ai(prompt)

    return {
        "has_syntax_error": syntax_error is not None,
        "syntax_error": syntax_error,
        "analysis": analysis,
    }