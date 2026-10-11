
from server.agents.command_agent import understand_command
from server.agents.error_detection_agent import detect_errors
from server.agents.code_correction_agent import correct_code
from server.services.llm_service import ask_ai


def process_command(command: str, code: str = "") -> str:
    """Coordinate the three agents based on the user's request."""

    # Agent 1: Understand the user's request
    task_result = understand_command(command)
    task = task_result.get("task", "general_question")

    output = [
        "COMMAND UNDERSTANDING AGENT",
        f"Task: {task}",
        f"Description: {task_result.get('description', command)}",
        "",
    ]

    # Tasks that require code
    if task in {"detect_errors", "correct_code", "explain_code"}:
        if not code.strip():
            return (
                "\n".join(output)
                + "Please paste your Python code into the code input area "
                  "and submit your command again."
            )

    # Agent 2: Detect errors
    if task in {"detect_errors", "correct_code"}:
        detection = detect_errors(code)

        output.extend([
            "ERROR DETECTION AGENT",
            f"Syntax error: {detection['syntax_error'] or 'None detected'}",
            "Analysis:",
            detection["analysis"],
            "",
        ])

        # Agent 3: Suggest corrections when explicitly requested,
        # or when a syntax error is detected.
        should_correct = (
            task == "correct_code"
            or detection["has_syntax_error"]
        )

        if should_correct:
            errors = (
                detection["syntax_error"]
                or detection["analysis"]
            )

            correction = correct_code(code, errors)

            output.extend([
                "CODE CORRECTION AGENT",
                correction["correction"],
                "",
                "Note: Review the proposed correction before using it.",
            ])

        return "\n".join(output)

    # Explain code without running error detection
    if task == "explain_code":
        explanation = ask_ai(
            "Explain the following Python code in beginner-friendly terms. "
            "Do not execute it.\n\n"
            f"```python\n{code}\n```"
        )
        output.extend(["CODE EXPLANATION", explanation])
        return "\n".join(output)

    # Generate code or answer general programming questions
    response = ask_ai(
        "You are CodeAssist AI, a programming assistant. "
        "Answer clearly and do not claim to have executed code.\n\n"
        f"User request: {command}"
    )

    output.extend(["AI RESPONSE", response])
    return "\n".join(output)