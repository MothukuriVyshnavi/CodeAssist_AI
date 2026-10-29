
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

    # Tasks that require source code
    if task in {"detect_errors", "correct_code", "explain_code"}:
        if not code.strip():
            return (
                "\n".join(output)
                + "Please paste your code into the code input area "
                  "and submit your command again."
            )

    # Agent 2: Detect errors
    if task in {"detect_errors", "correct_code"}:
        detection = detect_errors(code)
        language = detection.get("language", "unknown")

        findings = detection.get("findings", {})

        error_categories = [
            "syntax_errors",
            "undefined_names",
            "type_errors",
            "runtime_errors",
        ]

        warning_categories = [
            "logical_bugs",
        ]

        error_count = sum(
            len(findings.get(category, []))
            for category in error_categories
        )

        warning_count = sum(
        len(findings.get(category, []))
            for category in warning_categories
        )

        output.extend([
            "ERROR DETECTION AGENT",
            f"Detected language: {language}",
            f"Error Count: {error_count}",
            f"Warning Count: {warning_count}",
            "Analysis:",
            detection.get("analysis", "No analysis was returned."),
            "",
        ])

        # Agent 3: Suggest corrections when explicitly requested,
        # or when the detection agent reports a syntax error.
        should_correct = (
            task == "correct_code"
            or detection.get("has_syntax_error", False)
            or detection.get("has_errors", False)
        )

        
        if should_correct:
            # Pass all detected findings to the correction agent.
            findings = detection.get("findings", {})
            errors = (
                f"Detected language: {language}\n"
                f"Findings: {findings}\n"
                f"Analysis: {detection.get('analysis', '')}"
            )

            correction = correct_code(
                code,
                errors,
                language=language,
            )

            output.extend([
                "CODE CORRECTION AGENT",
                f"Correction generated: {correction.get('success', False)}",
                f"Language: {correction.get('language', language)}",
                "",
                "Proposed corrected code:",
                correction.get("corrected_code") or
                "No corrected code could be extracted.",
                "",
                "Explanation:",
                correction.get("explanation", ""),
                "",
                "Note: This is a proposal. Review and approve it before applying.",
            ])


        return "\n".join(output)

    # Explain code in its detected language
    if task == "explain_code":
        detection = detect_errors(code)
        language = detection.get("language", "unknown")

        explanation = ask_ai(
            "You are a programming tutor. Explain the following "
            f"{language} code in beginner-friendly terms. "
            "Do not execute it or modify the original code. "
            "If the language identification is uncertain, say so.\n\n"
            f"```text\n{code}\n```"
        )

        output.extend([
            f"CODE EXPLANATION ({language})",
            explanation,
        ])
        return "\n".join(output)

    # Generate code or answer general programming questions
    response = ask_ai(
        "You are CodeAssist, a programming assistant supporting "
        "Python, Java, C, C++, and SQL. Answer clearly and do not "
        "claim to have executed code.\n\n"
        f"User request: {command}"
    )

    output.extend(["AI RESPONSE", response])
    return "\n".join(output)
