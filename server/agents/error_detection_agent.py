
import ast
import re

from server.services.llm_service import ask_ai


def detect_language(code: str) -> str:
    """Identify the likely programming language."""

    text = code.strip()

    if not text:
        return "unknown"

        # SQL — also recognize common misspellings such as SELEC.
    if (
        re.search(
            r"\b(SELECT|SELEC)\b[\s\S]*\bFROM\b",
            text,
            re.IGNORECASE,
        )
        or re.search(
            r"\b(INSERT\s+INTO|UPDATE\s+\w+\s+SET|"
            r"DELETE\s+FROM|CREATE\s+TABLE|ALTER\s+TABLE)\b",
            text,
            re.IGNORECASE,
        )
    ):
        return "SQL"

    # Java
    if (
        re.search(r"\bpublic\s+class\s+\w+", text)
        or re.search(r"\bstatic\s+void\s+main\s*\(", text)
        or re.search(r"\bSystem\.out\.println\s*\(", text)
        or re.search(r"\bimport\s+java\.", text)
    ):
        return "Java"



    # C-specific indicators must be checked before general C++ rules.
    if (
        re.search(r"#\s*include\s*[<\"]stdio\.h[>\"]", text)
        or re.search(r"#\s*include\s*[<\"]stdlib\.h[>\"]", text)
        or re.search(r"#\s*include\s*[<\"]string\.h[>\"]", text)
        or re.search(r"#\s*include\s*[<\"]stdbool\.h[>\"]", text)
    ):
        return "C"

    # C++ indicators
    if (
        re.search(r"#\s*include\s*[<\"](?:iostream|string|vector|map|set|memory|algorithm)(?:\.h)?[>\"]", text)
        or re.search(r"\bstd::\w+", text)
        or re.search(r"\bcout\s*<<|\bcin\s*>>", text)
        or re.search(r"\busing\s+namespace\s+std\s*;", text)
    ):
        return "C++"

    # Additional C indicators
    if (
        re.search(r"\bprintf\s*\(", text)
        or re.search(r"\bscanf\s*\(", text)
        or re.search(r"\bint\s+main\s*\(\s*(void\s*)?\)", text)
    ):
        return "C"



    # Python
    if (
        re.search(r"^\s*def\s+\w+\s*\(", text, re.MULTILINE)
        or re.search(
            r"^\s*(if|elif|else|for|while|class|try|except)\b.*:\s*$",
            text,
            re.MULTILINE,
        )
        or re.search(
            r"^\s*(import\s+\w+|from\s+\w+\s+import)\b",
            text,
            re.MULTILINE,
        )
        or re.search(r"\bprint\s*\(", text)
    ):
        return "Python"

    return "Python"


def validate_sql_basics(code: str) -> str | None:
    """Catch common SQL statement keyword mistakes."""

    text = code.strip()

    # Remove leading SQL comments before checking the first statement.
    text = re.sub(r"^\s*(--[^\n]*\n\s*)+", "", text)

    patterns = [
        (
            r"(?is)^SELEC\b",
            "Possible SQL typo: SELECT is misspelled as SELEC.",
        ),
        (
            r"(?is)^SELECT\b(?![\s\S]*\bFROM\b)",
            "Possible SQL syntax error: SELECT statement is missing FROM.",
        ),
    ]

    for pattern, message in patterns:
        if re.search(pattern, text):
            return message

    return None


def validate_java_basics(code: str) -> str | None:
    """Catch a common Java error: a missing semicolon after println."""

    pattern = (
        r'System\.out\.println\s*\([^;\n]*\)\s*'
        r'(?=\s*(?:\}|$))'
    )

    if re.search(pattern, code):
        return (
            "Possible Java syntax error: missing semicolon "
            "after System.out.println(...)."
        )

    return None



def validate_c_basics(code: str) -> str | None:
    """Catch a missing semicolon after a simple printf statement."""

    pattern = (
        r'printf\s*\([^;\n}]*\)\s*'
        r'(?=\s+(?:return\b|[A-Za-z_]\w*\s*=|'
        r'printf\s*\(|[A-Za-z_]\w*\s*\())'
    )

    if re.search(pattern, code):
        return (
            "Possible C syntax error: missing semicolon "
            "after printf(...)."
        )

    return None




def validate_cpp_basics(code: str) -> str | None:
    """Catch a missing semicolon after a simple cout statement."""

    pattern = (
        r'\b(?:std::)?cout\s*<<[^;\n}]*'
        r'(?=\s+(?:return\b|std::|cout\b|'
        r'printf\s*\(|[A-Za-z_]\w*\s*=))'
    )

    if re.search(pattern, code):
        return (
            "Possible C++ syntax error: missing semicolon "
            "after a cout statement."
        )

    return None



def detect_errors(code: str) -> dict:
    """Validate Python syntax and analyze code in its likely language."""

    language = detect_language(code)
    if language == "SQL":
        sql_error = validate_sql_basics(code)
        if sql_error:
            return {
                "language": language,
                "has_syntax_error": True,
                "syntax_error": sql_error,
                "analysis": sql_error,
            }


    if language == "Java":
        java_error = validate_java_basics(code)
        if java_error:
            return {
                "language": language,
                "has_syntax_error": True,
                "syntax_error": java_error,
                "analysis": java_error,
            }


    if language == "C":
        c_error = validate_c_basics(code)
        if c_error:
            return {
                "language": language,
                "has_syntax_error": True,
                "syntax_error": c_error,
                "analysis": c_error,
            }


    if language == "C++":
        cpp_error = validate_cpp_basics(code)
        if cpp_error:
            return {
                "language": language,
                "has_syntax_error": True,
                "syntax_error": cpp_error,
                "analysis": cpp_error,
            }


    if not code.strip():
        return {
            "language": language,
            "has_syntax_error": False,
            "syntax_error": None,
            "analysis": "No code was provided to analyze.",
        }

    # Python has a real parser available in the standard library.
    if language == "Python":
        try:
            ast.parse(code)
        except SyntaxError as error:
            syntax_error = (
                f"Syntax error on line {error.lineno}: {error.msg}"
            )
            return {
                "language": language,
                "has_syntax_error": True,
                "syntax_error": syntax_error,
                "analysis": (
                    f"{syntax_error}. Review the indicated line."
                ),
            }

    prompt = f"""
You are the Error Detection Agent in CodeAssist.

Detected language: {language}

Analyze the code using {language} syntax rules.

Check for:
1. Syntax errors, including missing punctuation and delimiters.
2. Type errors and undefined names, where applicable.
3. Potential runtime risks and logical bugs.

Rules:
- Do not apply Python syntax rules to other languages.
- Report only errors supported by the supplied code.
- Do not rewrite or correct the code.
- Do not claim that a compiler was used.
- If uncertain, explicitly state the uncertainty.
- If no error is found, do not guarantee correctness.

Code:
```{language}
{code}
```

Return exactly these fields:
Language: {language}
Syntax errors: None detected OR a concise description of the suspected syntax error
Analysis: A concise explanation
"""

    analysis = ask_ai(prompt)

    # Parse the LLM response conservatively.
    # This is a suspected error, not compiler-confirmed validation.
    syntax_error = None
    has_syntax_error = False


    for line in analysis.splitlines():
        if line.strip().lower().startswith("syntax errors:"):
            value = line.split(":", 1)[1].strip()
            normalized = value.lower().strip(" []*.")

            no_error_phrases = (
                "none",
                "none detected",
                "no syntax errors",
                "no syntax errors detected",
                "no errors found",
            )

            is_no_error = (
                normalized in no_error_phrases
                or normalized.startswith("none detected ")
                or normalized.startswith("none found")
                or normalized.startswith("no syntax errors ")
                or normalized.startswith("no errors found")
                or "or a concise description" in normalized
            )

            if value and not is_no_error:
                syntax_error = value
                has_syntax_error = True

            break


    return {
        "language": language,
        "has_syntax_error": has_syntax_error,
        "syntax_error": syntax_error,
        "analysis": analysis,
    }
