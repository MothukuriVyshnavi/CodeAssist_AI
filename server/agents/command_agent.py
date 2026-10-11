
import json
from server.services.llm_service import ask_ai


def understand_command(command: str) -> dict:
    """Classify programming commands reliably."""

    text = command.lower().strip()

    # Rule-based classification for clear commands
    if any(word in text for word in [
        "find errors", "detect errors", "check errors",
        "debug", "bug", "error", "syntax error",
        "identify errors", "analyze errors",
    ]):
        task = "detect_errors"

    elif any(word in text for word in [
        "fix", "correct", "repair", "resolve",
        "correct the code",
    ]):
        task = "correct_code"

    elif any(word in text for word in [
        "explain", "describe", "what does",
        "how does this code",
    ]):
        task = "explain_code"

    elif any(word in text for word in [
        "write a program", "generate code",
        "create a function", "write code",
        "implement",
    ]):
        task = "generate_code"

    else:
        prompt = f"""
Classify this programming request into one category:
detect_errors, correct_code, explain_code,
generate_code, general_question.

Return only JSON:
{{"task": "category", "description": "short explanation"}}

Request: {command}
"""
        response = ask_ai(prompt)

        try:
            result = json.loads(response)
            allowed = {
                "detect_errors", "correct_code", "explain_code",
                "generate_code", "general_question",
            }

            if result.get("task") in allowed:
                return result
        except (json.JSONDecodeError, TypeError):
            pass

        task = "general_question"

    return {
        "task": task,
        "description": command,
    }