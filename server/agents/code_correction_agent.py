
from server.services.llm_service import ask_ai


def correct_code(code: str, errors: str) -> dict:
    """Generate corrected code and explain the changes."""

    prompt = f"""
You are the Code Correction Agent in CodeAssist AI.

Fix the reported errors in the supplied Python code.

Rules:
1. Preserve the original program's intended behavior.
2. Fix reported errors and avoid unrelated changes.
3. Return the complete corrected Python code.
4. Do not claim the code was tested or executed.
5. Separate your response into these sections:

CORRECTED_CODE:
Provide the complete corrected code inside a Python code block.

EXPLANATION:
Briefly explain the changes.

ORIGINAL CODE:
{code}

DETECTED ERRORS:
{errors}
"""

    response = ask_ai(prompt)

    return {
        "original_code": code,
        "correction": response,
    }