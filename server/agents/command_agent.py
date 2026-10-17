import json
import re

from server.services.llm_service import ask_ai


def understand_command(command: str) -> dict:
    """Classify the user's programming request."""

    text = command.lower().strip()

    # Correction requests take priority over general error checks.
    if re.search(r"\b(fix|correct|repair|resolve)\b", text):
        task = "correct_code"

    elif any(
        phrase in text
        for phrase in [
            "find errors",
            "detect errors",
            "check errors",
            "identify errors",
            "analyze errors",
            "debug",
            "syntax error",
            "runtime error",
        ]
    ) or re.search(r"\bbugs?\b|\berrors?\b", text):
        task = "detect_errors"

    elif any(
        phrase in text
        for phrase in [
            "explain",
            "describe",
            "what does",
            "how does this code",
        ]
    ):
        task = "explain_code"

    elif any(
        phrase in text
        for phrase in [
            "write a program",
            "generate code",
            "create a function",
            "write code",
            "implement",
        ]
    ):
        task = "generate_code"

    else:
        prompt = f"""
Classify this programming request into exactly one category:
detect_errors, correct_code, explain_code,
generate_code, general_question.

Return JSON only, using this format:
{{"task": "category", "description": "short explanation"}}

Request: {command}
"""

        response = ask_ai(prompt)

        try:
            # Also accept a JSON object wrapped in Markdown fences.
            match = re.search(r"\{.*\}", response, re.DOTALL)

            if match:
                result = json.loads(match.group(0))

                allowed = {
                    "detect_errors",
                    "correct_code",
                    "explain_code",
                    "generate_code",
                    "general_question",
                }

                if result.get("task") in allowed:
                    return {
                        "task": result["task"],
                        "description": result.get(
                            "description", command
                        ),
                    }

        except (json.JSONDecodeError, TypeError, AttributeError):
            pass

        task = "general_question"

    return {
        "task": task,
        "description": command,
    }