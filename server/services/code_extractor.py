
import json
import os
import time
from pathlib import Path

from server.services.screen_service import extract_text_from_screen

SNAPSHOT_PATH = (
    Path(os.getenv("TEMP", ".")) 
    / "CodeAssistCaptures"
    / "cursor_editor.json"
)

MAX_SNAPSHOT_AGE_SECONDS = 10


def extract_code_with_fallback(screenshot_path: str) -> str:
    """
    Prefer exact source code from the Cursor extension.
    If unavailable or stale, fall back to OCR.
    Set CODEASSIST_SOURCE=ocr to force OCR.
    """
    source_mode = os.getenv("CODEASSIST_SOURCE", "auto").strip().lower()

    if source_mode != "ocr":
        try:
            if SNAPSHOT_PATH.exists():
                snapshot = json.loads(
                    SNAPSHOT_PATH.read_text(encoding="utf-8")
                )

                timestamp_ms = int(snapshot.get("timestamp_ms", 0))
                age_seconds = (time.time() * 1000 - timestamp_ms) / 1000

                text = snapshot.get("text", "")
                language = snapshot.get("language_id", "unknown")
                file_name = snapshot.get("file_name", "unknown")

                if (
                    0 <= age_seconds <= MAX_SNAPSHOT_AGE_SECONDS
                    and isinstance(text, str)
                    and text.strip()
                ):
                    print(
                        f"[CodeExtractor] Using Cursor code: "
                        f"{file_name} ({language}), {len(text)} characters.",
                        flush=True,
                    )
                    return text

                print(
                    "[CodeExtractor] Cursor snapshot is stale or empty.",
                    flush=True,
                )

        except (OSError, ValueError, TypeError) as error:
            print(
                f"[CodeExtractor] Could not read Cursor snapshot: {error}",
                flush=True,
            )

    print("[CodeExtractor] Falling back to screen OCR.", flush=True)

    if not screenshot_path:
        return ""

    return extract_text_from_screen(screenshot_path) or ""
