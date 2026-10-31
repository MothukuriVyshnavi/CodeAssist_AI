
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

def _fix_c_use_after_free(code: str, errors: str):
    """Safely handle a simple printf-after-free pattern."""

    if not re.search(
        r"deallocuse|use.after.free|use after free",
        errors,
        re.IGNORECASE,
    ):
        return None

    lines = code.splitlines()

    for free_index, line in enumerate(lines):
        free_match = re.match(
            r"^(\s*)free\s*\(\s*(\w+)\s*\)\s*;\s*$",
            line,
        )

        if not free_match:
            continue

        pointer = free_match.group(2)

        # Find a printf statement accessing this pointer after free().
        for index in range(free_index + 1, len(lines)):
            access_pattern = (
                rf"\b{re.escape(pointer)}\s*\["
                rf"|\*\s*{re.escape(pointer)}\b"
                rf"|\b{re.escape(pointer)}\s*->"
            )

            if (
                re.search(r"\bprintf\s*\(", lines[index])
                and re.search(access_pattern, lines[index])
            ):
                # Move the required output operation before free().
                output_line = lines.pop(index)
                lines.insert(free_index, output_line)

                return "\n".join(lines)

    return None
def _fix_c_array_out_of_bounds(code: str, errors: str):
    """Fix simple constant-index out-of-bounds array accesses."""

    if not re.search(
        r"out.of.bounds|arrayindexoutofbounds|buffer overflow",
        errors,
        re.IGNORECASE,
    ):
        return None

    declarations = re.finditer(
        r"\b\w+\s+(\w+)\s*\[\s*(\d+)\s*\]",
        code,
    )

    corrected = code

    for declaration in declarations:
        array_name = declaration.group(1)
        array_size = int(declaration.group(2))

        if array_size <= 0:
            continue

        pattern = (
            rf"\b{re.escape(array_name)}\s*"
            rf"\[\s*(\d+)\s*\]"
        )

        corrected = re.sub(
            pattern,
            lambda match: (
                f"{array_name}[{array_size - 1}]"
                if int(match.group(1)) >= array_size
                else match.group(0)
            ),
            corrected,
        )

    return corrected if corrected != code else None

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

    # Deterministic C correction: Use After Free.
    if language == "c":
        deterministic_code = _fix_c_use_after_free(code, errors)

        if deterministic_code:
            return {
                "original_code": code,
                "correction": deterministic_code,
                "corrected_code": deterministic_code,
                "explanation": (
                    "Moved the required printf operation before free() "
                    "so the allocated memory is accessed before release."
                ),
                "language": language,
                "success": True,
            }
    # Deterministic C correction: Array Out of Bounds.
    if language == "c":
        deterministic_code = _fix_c_array_out_of_bounds(code, errors)

        if deterministic_code:
            return {
                "original_code": code,
                "correction": deterministic_code,
                "corrected_code": deterministic_code,
                "explanation": (
                    "Corrected array indexes that exceeded the declared "
                    "array size. Array indexing starts at zero."
                ),
                "language": language,
                "success": True,
            }

    # Deterministic C correction: Null Pointer Dereference.
    if (
        language == "c"
        and re.search(
            r"nullpointer|null\.dereference|null pointer dereference",
            errors,
            re.IGNORECASE,
        )
    ):
        lines = code.splitlines()

        for index, line in enumerate(lines):
            match = re.match(
                r"^(\s*)printf\s*\((.*)\)\s*;\s*$",
                line,
            )

            if not match:
                continue

            indentation = match.group(1)
            statement = line.strip()

            if not re.search(
                r"\*\s*ptr\b|\bptr\s*\[|\bptr\s*->",
                statement,
            ):
                continue

            # Only apply this rule when ptr is explicitly initialized to NULL.
            if not re.search(
                r"\bptr\s*=\s*NULL\b",
                code,
            ):
                break

            replacement = [
                f"{indentation}if (ptr != NULL) {{",
                f"{indentation}    {statement}",
                f"{indentation}}} else {{",
                f'{indentation}    printf("Pointer is NULL\\n");',
                f"{indentation}}}",
            ]

            lines[index:index + 1] = replacement
            deterministic_code = "\n".join(lines)

            return {
                "original_code": code,
                "correction": deterministic_code,
                "corrected_code": deterministic_code,
                "explanation": (
                    "Added a NULL check before dereferencing ptr. "
                    "The program now handles the NULL case safely."
                ),
                "language": language,
                "success": True,
            }

    # AI correction rules.
    correction_rules = ""

    if language == "c":
        correction_rules = """
IMPORTANT C MEMORY SAFETY RULES:

1. Never dereference a NULL pointer.
2. Check pointers before accessing their memory.
3. Never access memory after free().
4. Preserve the original program's intended behavior.
5. Do not remove required operations unnecessarily.
"""

    # Always construct the prompt, regardless of error category.
    prompt = f"""You are an expert programming code fixer.
Language: {language}

Fix the reported error in the original code.
Preserve its intended behavior.
Do not invent unrelated changes.

{correction_rules}

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
