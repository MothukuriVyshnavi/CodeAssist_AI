
import json
import os
import time
from pathlib import Path

from PIL import Image

from server.services.screen_service import (
    extract_text_from_image,
    extract_text_from_screen,
)

SNAPSHOT_PATH = (
    Path(os.getenv("TEMP", "."))
    / "CodeAssistCaptures"
    / "cursor_editor.json"
)

MAX_SNAPSHOT_AGE_SECONDS = 10


def extract_code_with_fallback(
    screenshot_path: str = "",
    screen_image: Image.Image | None = None,
) -> str:
    """
    Prefer exact source code from the Cursor editor bridge.
    If unavailable or stale, use OCR on an in-memory image.
    A screenshot path remains supported for backward compatibility.

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
                age_seconds = (
                    time.time() * 1000 - timestamp_ms
                ) / 1000

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
                        f"{file_name} ({language}), "
                        f"{len(text)} characters.",
                        flush=True,
                    )
                    return text

                print(
                    "[CodeExtractor] Cursor snapshot is stale or empty.",
                    flush=True,
                )

        except (OSError, ValueError, TypeError) as error:
            print(
                f"[CodeExtractor] Could not read Cursor snapshot: "
                f"{error}",
                flush=True,
            )

    print("[CodeExtractor] Falling back to screen OCR.", flush=True)

    if screen_image is not None:
        return extract_text_from_image(screen_image) or ""

    if screenshot_path:
        return extract_text_from_screen(screenshot_path) or ""

    print(
        "[CodeExtractor] No screen image or screenshot path available.",
        flush=True,
    )
    return ""
