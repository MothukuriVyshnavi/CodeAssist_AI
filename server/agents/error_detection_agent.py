
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

Analyze the following Python code.
Identify likely bugs, logic problems, and suspicious code.
Do not rewrite or correct the code.
If no problems are apparent, say so.

Code:
```python
{code}
```

Return a clear, concise analysis.
"""

    analysis = ask_ai(prompt)

    return {
        "has_syntax_error": syntax_error is not None,
        "syntax_error": syntax_error,
        "analysis": analysis,
    }