
from server.services.llm_service import ask_ai


def correct_code(code: str, errors: str) -> dict:
    """Generate corrected code and explain the changes."""

    
    prompt = f"""
You are the Code Correction Agent in CodeAssist AI.

Fix the actual errors in the supplied Python code.

Rules:
1. Preserve the original program's intended behavior.
2. Use the detected errors as the primary guide.
3. Explain only changes that were actually necessary.
4. Do not invent errors.
5. Do not say indentation was wrong unless the original
   code actually had an indentation error.
6. Do not describe blank lines as errors unless they cause
   a real problem.
7. Return the complete corrected Python code.
8. Do not claim that the code was executed or tested.

Use exactly this format:

CORRECTED_CODE:
[Python code inside a Python code block]

EXPLANATION:
[State the exact error and how it was fixed.]

Original code:
{code}

Detected errors:
{errors}
"""

    response = ask_ai(prompt)

    return {
        "original_code": code,
        "correction": response,
    }