import ast
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from server.services.language_detector import detect_sql_dialect


def _result(
    language,
    tool,
    available,
    has_errors=False,
    syntax_error=None,
    diagnostics="",
):
    return {
        "language": language,
        "tool": tool,
        "available": available,
        "has_errors": has_errors,
        "has_syntax_error": (
            language == "python" and has_errors
        ),
        "syntax_error": syntax_error,
        "diagnostics": diagnostics,
    }


def _run_compiler(command, source_path, language, timeout=20):
    """Run a compiler in check-only mode. Never execute the source."""

    try:
        completed = subprocess.run(
            command + [str(source_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return _result(
            language,
            "compiler",
            True,
            diagnostics="Compiler check timed out.",
        )
    except OSError as error:
        return _result(
            language,
            "compiler",
            False,
            diagnostics=f"Could not start the compiler: {error}",
        )

    details = "\n".join(
        part.strip()
        for part in (completed.stdout, completed.stderr)
        if part and part.strip()
    )

    if completed.returncode != 0:
        details = details or "The compiler reported an error."

        return _result(
            language,
            "compiler",
            True,
            has_errors=True,
            syntax_error=details,
            diagnostics=details,
        )

    return _result(
        language,
        "compiler",
        True,
        diagnostics=details or "No compiler errors reported.",
    )


def _check_python(code):
    try:
        ast.parse(code)
    except SyntaxError as error:
        message = (
            f"Syntax error on line {error.lineno}: {error.msg}"
        )
        return _result(
            "python",
            "Python AST",
            True,
            has_errors=True,
            syntax_error=message,
            diagnostics=message,
        )

    return _result(
        "python",
        "Python AST",
        True,
        diagnostics="No Python syntax errors detected.",
    )


def _check_c(code):
    compiler = shutil.which("gcc") or shutil.which("clang")

    if not compiler:
        return _result(
            "c",
            "GCC or Clang",
            False,
            diagnostics=(
                "C compiler not found. Install GCC or Clang and "
                "make sure the compiler is available on PATH."
            ),
        )

    with tempfile.TemporaryDirectory(prefix="codeassist_c_") as folder:
        source_path = Path(folder) / "main.c"
        source_path.write_text(code, encoding="utf-8")

        return _run_compiler(
            [compiler, "-fsyntax-only"],
            source_path,
            "c",
        )


def _check_cpp(code):
    compiler = (
        shutil.which("g++")
        or shutil.which("clang++")
    )

    if not compiler:
        return _result(
            "cpp",
            "G++ or Clang++",
            False,
            diagnostics=(
                "C++ compiler not found. Install G++ or Clang++ "
                "and make sure it is available on PATH."
            ),
        )

    with tempfile.TemporaryDirectory(prefix="codeassist_cpp_") as folder:
        source_path = Path(folder) / "main.cpp"
        source_path.write_text(code, encoding="utf-8")

        return _run_compiler(
            [compiler, "-std=c++17", "-fsyntax-only"],
            source_path,
            "cpp",
        )


def _check_java(code):
    compiler = shutil.which("javac")

    if not compiler:
        return _result(
            "java",
            "Java JDK javac",
            False,
            diagnostics=(
                "Java compiler javac was not found. Install a JDK "
                "and make sure its bin directory is on PATH."
            ),
        )

    # Match the filename to a public top-level Java type if present.
    type_match = re.search(
        r"\bpublic\s+"
        r"(?:(?:abstract|final|sealed|non-sealed)\s+)*"
        r"(?:class|interface|enum|record)\s+"
        r"([A-Za-z_$][\w$]*)",
        code,
    )

    if type_match:
        type_name = type_match.group(1)
    else:
        type_match = re.search(
            r"\b(?:class|interface|enum|record)\s+"
            r"([A-Za-z_$][\w$]*)",
            code,
        )
        type_name = (
            type_match.group(1)
            if type_match
            else "CodeAssistTemp"
        )

    package_match = re.search(
        r"^\s*package\s+([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\s*;",
        code,
        re.MULTILINE,
    )

    with tempfile.TemporaryDirectory(prefix="codeassist_java_") as folder:
        root = Path(folder)
        source_dir = root

        if package_match:
            source_dir = root.joinpath(
                *package_match.group(1).split(".")
            )
            source_dir.mkdir(parents=True, exist_ok=True)

        source_path = source_dir / f"{type_name}.java"
        source_path.write_text(code, encoding="utf-8")

        return _run_compiler(
            [compiler, "-Xlint:all", "-d", str(root)],
            source_path,
            "java",
        )


def _check_sql(code, command=""):
    try:
        import sqlglot
    except ImportError:
        return _result(
            "sql",
            "SQLGlot",
            False,
            diagnostics=(
                "SQLGlot is not installed. Run: "
                "python -m pip install sqlglot"
            ),
        )

    dialect = detect_sql_dialect(command)

    try:
        sqlglot.parse(code, read=dialect)
    except Exception as error:
        message = f"SQL parsing error: {error}"
        return _result(
            "sql",
            "SQLGlot",
            True,
            has_errors=True,
            syntax_error=message,
            diagnostics=message,
        )

    dialect_name = dialect or "default SQL dialect"
    return _result(
        "sql",
        "SQLGlot",
        True,
        diagnostics=(
            f"SQL parsing succeeded using {dialect_name}. "
            "This does not guarantee that the query will execute "
            "successfully against a particular database."
        ),
    )


def diagnose_code(code, language, command=""):
    """Choose the appropriate diagnostic tool for the language."""

    language = (language or "unknown").lower()

    if not code.strip():
        return _result(
            language,
            "none",
            False,
            diagnostics="No code was supplied.",
        )

    if language == "python":
        return _check_python(code)

    if language == "c":
        return _check_c(code)

    if language == "cpp":
        return _check_cpp(code)

    if language == "java":
        return _check_java(code)

    if language == "sql":
        return _check_sql(code, command)

    return _result(
        "unknown",
        "none",
        False,
        diagnostics=(
            "Could not identify the programming language. "
            "Specify Python, C, C++, Java, or SQL in your command."
        ),
    )