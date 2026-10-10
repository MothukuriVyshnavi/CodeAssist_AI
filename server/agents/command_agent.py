
import json
from server.services.llm_service import ask_ai


def understand_command(command: str) -> dict:
    """Identify the type of programming request."""

    prompt = f"""
You are the Command Understanding Agent in CodeAssist AI.

Classify the user's request into exactly one category:
- detect_errors
- correct_code
- explain_code
- generate_code
- general_question

Return only a valid JSON object in this format:
{{
    "task": "one_category",
    "description": "short explanation"
}}

User request: {command}
"""

    response = ask_ai(prompt)

    try:
        result = json.loads(response)

        allowed_tasks = {
            "detect_errors",
            "correct_code",
            "explain_code",
            "generate_code",
            "general_question",
        }

        if result.get("task") not in allowed_tasks:
            raise ValueError("Invalid task category")

        return result

    except (json.JSONDecodeError, ValueError):
        return {
            "task": "general_question",
            "description": command,
        }