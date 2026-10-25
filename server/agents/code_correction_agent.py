
import re

from server.services.llm_service import ask_ai


def _extract_code(response: str) -> str:
    """Extract corrected code from a model response."""

    if not response:
        return ""

    # Prefer a code block following CORRECTED_CODE.
    match = re.search(
        r"CORRECTED_CODE\s*:\s*```[^\n`]*\n(.*?)```",
        response,
        re.IGNORECASE | re.DOTALL,
    )
    if match:
        return match.group(1).strip()

    # Accept a normal fenced code block.
    match = re.search(
        r"```(?:python|java|c\+\+|cpp|c|sql)?\s*\n(.*?)```",
        response,
        re.IGNORECASE | re.DOTALL,
    )
    if match:
        return match.group(1).strip()

    return ""


def correct_code(code: str, errors: str, language: str = "python") -> dict:
    """Generate a proposed correction without applying it to any file."""

    code = str(code or "").strip()
    errors = str(errors or "").strip()
    language = str(language or "python").strip().lower()

    if not code:
        return {
            "original_code": code,
            "correction": "",
            "corrected_code": "",
            "explanation": "No source code was provided.",
            "language": language,
            "success": False,
        }

    prompt = f"""You are a programming code fixer.
Language: {language}

Fix the reported error in the original code.
Preserve its intended behavior. Do not invent unrelated changes.
Return the complete corrected program.

Use exactly this format:
CORRECTED_CODE:
```{language}
your complete corrected program here
```
EXPLANATION:
Briefly explain the change.

ORIGINAL CODE:
{code}

REPORTED ERRORS:
{errors}
"""

    try:
        response = str(ask_ai(prompt) or "").strip()
        corrected = _extract_code(response)

        explanation_match = re.search(
            r"EXPLANATION\s*:\s*(.*)",
            response,
            re.IGNORECASE | re.DOTALL,
        )
        explanation = (
            explanation_match.group(1).strip()
            if explanation_match
            else (
                "The model did not provide a separate explanation."
                if corrected
                else response
            )
        )

        return {
            "original_code": code,
            "correction": response,
            "corrected_code": corrected,
            "explanation": explanation,
            "language": language,
            "success": bool(corrected),
        }

    except Exception as exc:
        return {
            "original_code": code,
            "correction": "",
            "corrected_code": "",
            "explanation": f"Correction generation failed: {exc}",
            "language": language,
            "success": False,
        }
