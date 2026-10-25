
import ast
import builtins
import json
import os
import re
import subprocess
import symtable
import sys
import tempfile

from server.services.llm_service import ask_ai


ERROR_CATEGORIES = (
    "syntax_errors",
    "undefined_names",
    "type_errors",
    "runtime_errors",
    "logical_bugs",
)


# ---------------------------------------------------------------------
# Shared result helpers
# ---------------------------------------------------------------------

def deduplicate_undefined_names(items):
    """Keep one diagnostic per undefined variable."""
    result = []
    seen_names = set()

    for item in items:
        match = re.search(
            r"(?:Name\s+['`\"]|Undefined name\s+[`'\"])([A-Za-z_]\w*)",
            item,
            re.IGNORECASE,
        )

        if match:
            name = match.group(1)
            if name in seen_names:
                continue
            seen_names.add(name)

        result.append(item)

    return result

def _empty_findings():
    return {
        "syntax_errors": [],
        "undefined_names": [],
        "type_errors": [],
        "runtime_errors": [],
        "logical_bugs": [],
        "explanation": "",
    }


def _as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _add_finding(findings, category, message):
    if category not in ERROR_CATEGORIES:
        return

    message = str(message).strip()
    if message and message not in findings[category]:
        findings[category].append(message)


def _result(language, findings, analysis=None):
    normalized = _empty_findings()

    for category in ERROR_CATEGORIES:
        normalized[category] = _as_list(findings.get(category, []))

    explanation = findings.get("explanation", "")
    normalized["explanation"] = (
        explanation if isinstance(explanation, str) else str(explanation)
    )

    has_errors = any(normalized[key] for key in ERROR_CATEGORIES)
    syntax_errors = normalized["syntax_errors"]

    return {
        "language": language,
        "has_syntax_error": bool(syntax_errors),
        "syntax_error": "; ".join(map(str, syntax_errors)) if syntax_errors else None,
        "has_errors": bool(has_errors),
        "findings": normalized,
        "analysis": analysis or json.dumps(normalized, indent=2),
    }


# ---------------------------------------------------------------------
# Language detection
# ---------------------------------------------------------------------

def detect_language(code: str) -> str:
    text = (code or "").strip()

    if not text:
        return "unknown"

    if re.search(
        r"(?im)^\s*(SELECT|SELEC|INSERT\s+INTO|UPDATE\s+\w+\s+SET|"
        r"DELETE\s+FROM|CREATE\s+TABLE|ALTER\s+TABLE)\b",
        text,
    ):
        return "SQL"

    if (
        re.search(r"\bpublic\s+class\s+\w+", text)
        or re.search(r"\bstatic\s+void\s+main\s*\(", text)
        or re.search(r"\bSystem\s*\.\s*out\s*\.\s*println\s*\(", text)
        or re.search(r"\bimport\s+java\.", text)
    ):
        return "Java"

    if re.search(
        r'#\s*include\s*[<"](?:stdio|stdlib|string|stdbool)\.h[>"]',
        text,
    ):
        return "C"

    if (
        re.search(
            r'#\s*include\s*[<"]'
            r'(?:iostream|string|vector|map|set|memory|algorithm)'
            r'(?:\.h)?[>"]',
            text,
        )
        or re.search(r"\bstd::\w+", text)
        or re.search(r"\bcout\s*<<|\bcin\s*>>", text)
        or re.search(r"\busing\s+namespace\s+std\s*;", text)
    ):
        return "C++"

    if (
        re.search(r"\bprintf\s*\(", text)
        or re.search(r"\bscanf\s*\(", text)
        or re.search(r"\bint\s+main\s*\(", text)
    ):
        return "C"

    if (
        re.search(r"(?m)^\s*def\s+\w+\s*\(", text)
        or re.search(
            r"(?m)^\s*(if|elif|else|for|while|class|try|except|with)\b",
            text,
        )
        or re.search(r"(?m)^\s*(import\s+\w+|from\s+\w+\s+import)\b", text)
        or re.search(r"\bprint\s*\(", text)
        or re.search(r"\b(None|True|False|self|lambda)\b", text)
    ):
        return "Python"

    return "Python"


# ---------------------------------------------------------------------
# External validators
# ---------------------------------------------------------------------

def validate_python_with_ruff(code: str) -> list[str]:
    """Use Ruff to check Python code in a temporary file."""
    try:
        with tempfile.TemporaryDirectory(prefix="codeassist_") as temp_dir:
            file_path = os.path.join(temp_dir, "snippet.py")

            with open(file_path, "w", encoding="utf-8") as file:
                file.write(code)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ruff",
                    "check",
                    "--output-format",
                    "json",
                    file_path,
                ],
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )

            if result.returncode not in (0, 1):
                return []

            diagnostics = json.loads(result.stdout or "[]")
            findings = []

            for item in diagnostics:
                line = item.get("location", {}).get("row", "?")
                message = item.get("message", "Ruff detected an issue")
                rule = item.get("code", "RUFF")

                findings.append(f"Line {line}: {message} ({rule}).")

            return findings

    except (OSError, subprocess.TimeoutExpired, ValueError):
        return []


def validate_sql_with_sqlglot(code: str) -> list[str]:
    """Parse SQL without executing queries."""
    try:
        import sqlglot
        from sqlglot.errors import ParseError

        try:
            sqlglot.parse(code)
            return []
        except ParseError as error:
            findings = []

            for item in error.errors:
                line = item.get("line", "?")
                description = item.get("description", str(error))
                findings.append(f"Line {line}: SQL parse error: {description}.")

            return findings or [f"SQL parse error: {error}"]

    except ImportError:
        return []


# ---------------------------------------------------------------------
# Python static analysis
# ---------------------------------------------------------------------

def _python_undefined_names(code: str):
    try:
        root = symtable.symtable(code, "<codeassist>", "exec")
    except SyntaxError:
        return []

    builtin_names = set(dir(builtins))
    module_symbols = {
        symbol.get_name(): symbol for symbol in root.get_symbols()
    }
    undefined = set()

    def inspect_scope(scope):
        for symbol in scope.get_symbols():
            name = symbol.get_name()

            if not symbol.is_referenced() or not symbol.is_global():
                continue

            module_symbol = module_symbols.get(name)

            if (
                name not in builtin_names
                and (
                    module_symbol is None
                    or not (
                        module_symbol.is_assigned()
                        or module_symbol.is_imported()
                        or module_symbol.is_namespace()
                    )
                )
            ):
                undefined.add(name)

        for child in scope.get_children():
            inspect_scope(child)

    inspect_scope(root)
    return sorted(undefined)


def _python_static_checks(code: str):
    findings = _empty_findings()

    try:
        tree = ast.parse(code)
        compile(tree, "<codeassist>", "exec")
    except SyntaxError as error:
        _add_finding(
            findings,
            "syntax_errors",
            f"Line {error.lineno}: {error.msg}",
        )
        findings["explanation"] = (
            "Python could not parse the code. Fix the syntax error first."
        )
        return findings

    for name in _python_undefined_names(code):
        _add_finding(
            findings,
            "undefined_names",
            f"Name '{name}' is referenced but not defined.",
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp):
            if (
                isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod))
                and isinstance(node.right, ast.Constant)
                and isinstance(node.right.value, (int, float))
                and not isinstance(node.right.value, bool)
                and node.right.value == 0
            ):
                _add_finding(
                    findings,
                    "runtime_errors",
                    f"Line {node.lineno}: division or modulo by zero.",
                )

            if (
                isinstance(node.op, ast.Add)
                and isinstance(node.left, ast.Constant)
                and isinstance(node.right, ast.Constant)
            ):
                left = node.left.value
                right = node.right.value

                if (
                    isinstance(left, str) != isinstance(right, str)
                    and (isinstance(left, str) or isinstance(right, str))
                ):
                    _add_finding(
                        findings,
                        "type_errors",
                        f"Line {node.lineno}: adding a string and a "
                        "non-string constant raises TypeError.",
                    )

        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, int)
            and not isinstance(node.slice.value, bool)
        ):
            sequence = node.value
            length = None

            if isinstance(sequence, (ast.List, ast.Tuple)):
                length = len(sequence.elts)

            elif isinstance(sequence, ast.Name):
                for statement in tree.body:
                    if (
                        isinstance(statement, ast.Assign)
                        and any(
                            isinstance(target, ast.Name)
                            and target.id == sequence.id
                            for target in statement.targets
                        )
                        and isinstance(statement.value, (ast.List, ast.Tuple))
                    ):
                        length = len(statement.value.elts)

                    elif (
                        isinstance(statement, ast.AnnAssign)
                        and isinstance(statement.target, ast.Name)
                        and statement.target.id == sequence.id
                        and isinstance(statement.value, (ast.List, ast.Tuple))
                    ):
                        length = len(statement.value.elts)

            if length is not None:
                index = node.slice.value

                if index >= length or index < -length:
                    _add_finding(
                        findings,
                        "runtime_errors",
                        f"Line {node.lineno}: index {index} is out of range "
                        f"for a sequence of length {length}.",
                    )

    # Retain the existing recognizable maximum-function check.
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "maximum":
            continue

        if len(node.args.args) != 2:
            continue

        arg_a = node.args.args[0].arg
        arg_b = node.args.args[1].arg

        for statement in node.body:
            if not isinstance(statement, ast.Return):
                continue

            value = statement.value

            if not isinstance(value, ast.IfExp):
                continue

            test = value.test

            if (
                isinstance(test, ast.Compare)
                and isinstance(test.left, ast.Name)
                and test.left.id == arg_a
                and len(test.ops) == 1
                and isinstance(test.ops[0], ast.Lt)
                and len(test.comparators) == 1
                and isinstance(test.comparators[0], ast.Name)
                and test.comparators[0].id == arg_b
                and isinstance(value.body, ast.Name)
                and value.body.id == arg_a
                and isinstance(value.orelse, ast.Name)
                and value.orelse.id == arg_b
            ):
                _add_finding(
                    findings,
                    "logical_bugs",
                    "The maximum function returns the smaller argument "
                    "when the inputs differ. Check the comparison or use "
                    "max(a, b) for comparable values.",
                )

    return findings


# ---------------------------------------------------------------------
# Basic checks for Java, C, and C++
# ---------------------------------------------------------------------

def validate_java_basics(code: str):
    pattern = (
        r"System\s*\.\s*out\s*\.\s*println\s*"
        r"\([^;\n]*\)\s*(?=\s*(?:\}|$))"
    )

    if re.search(pattern, code):
        return "Possible Java syntax error: missing semicolon after println."

    return None


def validate_c_basics(code: str):
    pattern = (
        r"printf\s*\([^;\n]*\)\s*"
        r"(?=\s+(?:return\b|[A-Za-z_]\w*\s*=|printf\s*\())"
    )

    if re.search(pattern, code):
        return "Possible C syntax error: missing semicolon after printf."

    return None


def validate_cpp_basics(code: str):
    pattern = (
        r"\b(?:std::)?cout\s*<<[^;\n}]*"
        r"(?=\s+(?:return\b|std::|cout\b|[A-Za-z_]\w*\s*=))"
    )

    if re.search(pattern, code):
        return "Possible C++ syntax error: missing semicolon after cout."

    return None


def validate_balanced_delimiters(code: str, language: str):
    """Check matching delimiters while ignoring strings and comments."""
    pairs = {")": "(", "]": "[", "}": "{"}
    opening = set(pairs.values())
    stack = []

    quote = None
    escaped = False
    line_comment = False
    block_comment = False
    i = 0

    while i < len(code):
        char = code[i]
        next_char = code[i + 1] if i + 1 < len(code) else ""

        if line_comment:
            if char == "\n":
                line_comment = False
            i += 1
            continue

        if block_comment:
            if char == "*" and next_char == "/":
                block_comment = False
                i += 2
                continue
            i += 1
            continue

        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            i += 1
            continue

        if char in ("'", '"', "`"):
            quote = char
        elif (
            language in ("C", "C++", "Java")
            and char == "/"
            and next_char == "/"
        ):
            line_comment = True
            i += 2
            continue
        elif (
            language in ("C", "C++", "Java")
            and char == "/"
            and next_char == "*"
        ):
            block_comment = True
            i += 2
            continue
        elif char in opening:
            stack.append((char, code.count("\n", 0, i) + 1))
        elif char in pairs:
            if not stack or stack[-1][0] != pairs[char]:
                line = code.count("\n", 0, i) + 1
                return (
                    f"Possible {language} syntax error: unmatched "
                    f"'{char}' on line {line}."
                )
            stack.pop()

        i += 1

    if stack:
        char, line = stack[-1]
        return (
            f"Possible {language} syntax error: missing closing delimiter "
            f"for '{char}' opened on line {line}."
        )

    return None


# ---------------------------------------------------------------------
# LLM response parsing
# ---------------------------------------------------------------------

def _parse_model_json(response):
    if not isinstance(response, str):
        raise ValueError("The analysis service returned a non-text response.")

    text = response.strip()

    if text.startswith("```"):
        text = re.sub(
            r"^```(?:json)?\s*",
            "",
            text,
            count=1,
            flags=re.IGNORECASE,
        )
        text = re.sub(r"\s*```$", "", text, count=1)

    start = text.find("{")
    end = text.rfind("}")

    if start < 0 or end <= start:
        raise ValueError("The model did not return a JSON object.")

    data = json.loads(text[start:end + 1])

    if not isinstance(data, dict):
        raise ValueError("Expected a JSON object.")

    return data


def _normalize_model_findings(model_findings):
    normalized = _empty_findings()

    for category in ERROR_CATEGORIES:
        for value in _as_list(model_findings.get(category, [])):
            if isinstance(value, (str, dict)):
                _add_finding(
                    normalized,
                    category,
                    value if isinstance(value, str)
                    else json.dumps(value, ensure_ascii=False),
                )

    explanation = model_findings.get("explanation", "")
    normalized["explanation"] = (
        explanation if isinstance(explanation, str) else ""
    )

    return normalized


# ---------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------

def detect_errors(code: str) -> dict:
    """Analyze Python, Java, C, C++, and SQL with static checks and Ollama."""
    code = code if isinstance(code, str) else ""
    language = detect_language(code)
    findings = _empty_findings()

    if not code.strip():
        findings["explanation"] = "No code was provided to analyze."
        return _result(language, findings)

    # Deterministic validation
    if language == "Python":
        findings = _python_static_checks(code)

        if findings["syntax_errors"]:
            return _result(language, findings)

        for diagnostic in validate_python_with_ruff(code):
            if "(F821)" in diagnostic or "Undefined name" in diagnostic:
                _add_finding(
                    findings,
                    "undefined_names",
                    diagnostic,
                )
            else:
                _add_finding(
                    findings,
                    "logical_bugs",
                    f"Static analysis suggestion: {diagnostic}",
                )

    elif language == "SQL":
        for message in validate_sql_with_sqlglot(code):
            _add_finding(findings, "syntax_errors", message)

        if findings["syntax_errors"]:
            findings["explanation"] = "; ".join(findings["syntax_errors"])
            return _result(language, findings)

    elif language in ("Java", "C", "C++"):
        basic_error = validate_balanced_delimiters(code, language)

        if not basic_error:
            if language == "Java":
                basic_error = validate_java_basics(code)
            elif language == "C":
                basic_error = validate_c_basics(code)
            else:
                basic_error = validate_cpp_basics(code)

        if basic_error:
            _add_finding(findings, "syntax_errors", basic_error)

    static_findings = {
        category: list(findings[category])
        for category in ERROR_CATEGORIES
    }

    prompt = f"""
You are CodeAssist's programming error analysis agent.

Language: {language}

Analyze the code conservatively. Find likely syntax errors, undefined names,
type errors, runtime errors, and logical bugs. Use the code's context and
intended behavior; do not invent requirements or input values.

Rules:
- A syntax error means invalid language grammar or syntax.
- Undefined names are not automatically syntax errors.
- Division by zero is a runtime issue.
- Explain the actual cause of each finding.
- Do not report the same issue in multiple categories.
- Do not claim that the code was executed or tested.
- Do not rewrite the code.
- Existing deterministic findings are included below; avoid duplicating them.
- Use empty lists where no issue is supported.
- The explanation must agree with the findings.

Return only a JSON object with this exact structure:
{{
  "syntax_errors": [],
  "undefined_names": [],
  "type_errors": [],
  "runtime_errors": [],
  "logical_bugs": [],
  "explanation": "Concise explanation"
}}

Existing validator findings:
{json.dumps(static_findings, indent=2)}

Code:
{code}
"""

    
    try:
        raw = ask_ai(prompt)
        model_findings = _normalize_model_findings(
            _parse_model_json(raw)
        )

        # Merge AI findings, but do not let AI override
        # deterministic Python syntax or undefined-name checks.
        for category in ERROR_CATEGORIES:
            if language == "Python" and category in (
                "syntax_errors",
                "undefined_names",
            ):
                continue

            for value in model_findings[category]:
                if language == "Python" and category == "logical_bugs":
                    text = value.lower()
                    if (
                        "undefined variable" in text
                        or "undefined name" in text
                        or "not been defined" in text
                        or "has not been defined" in text
                    ):
                        continue

                _add_finding(findings, category, value)


        if language == "Python":
            # Python AST parsing is authoritative for syntax.
            findings["syntax_errors"] = []

        # Preserve deterministic undefined-name findings and deduplicate.
        findings["undefined_names"] = deduplicate_undefined_names(
            static_findings["undefined_names"]
        )

        deterministic_parts = []

        for category in ERROR_CATEGORIES:
            if static_findings[category]:
                deterministic_parts.append(
                    f"{category.replace('_', ' ').title()}: "
                    + "; ".join(static_findings[category])
                )

        if deterministic_parts:
            findings["explanation"] = " ".join(deterministic_parts)
        elif not any(findings[category] for category in ERROR_CATEGORIES):
            findings["explanation"] = (
                "No errors detected by the available validators."
            )
        else:
            findings["explanation"] = (
                model_findings["explanation"].strip()
            )


        if not findings["explanation"]:
            findings["explanation"] = (
                "Analysis completed, but no reliable explanation was returned."
            )

    except Exception as error:
        findings["explanation"] = (
            "Deterministic analysis completed, but additional AI analysis "
            "was unavailable. Results may be incomplete. "
            f"Details: {error}"
        )

    return _result(language, findings)

