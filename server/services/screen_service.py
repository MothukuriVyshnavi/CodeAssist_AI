import os
import tempfile
from datetime import datetime
from pathlib import Path

import pytesseract
from mss import MSS
from PIL import Image, ImageOps


def capture_screen() -> str:
    """Capture the primary monitor and return the screenshot path."""

    capture_dir = Path(tempfile.gettempdir()) / "CodeAssistCaptures"
    capture_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    screenshot_path = capture_dir / f"screen_{timestamp}.png"

    with MSS() as screen:
        screenshot = screen.grab(screen.primary_monitor)
        image = Image.frombytes(
            "RGB",
            screenshot.size,
            screenshot.rgb,
        )
        image.save(screenshot_path)

    return str(screenshot_path)


def extract_text_from_screen(screenshot_path: str) -> str:
    """Use Tesseract OCR to extract visible text from a screenshot."""

    configured_path = os.getenv("TESSERACT_CMD")

    if configured_path:
        pytesseract.pytesseract.tesseract_cmd = configured_path
    else:
        default_path = Path(
            r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        )
        if default_path.exists():
            pytesseract.pytesseract.tesseract_cmd = str(default_path)

    try:
        with Image.open(screenshot_path) as image:
            image = ImageOps.autocontrast(image.convert("L"))

            # Enlarge small text to help OCR.
            image = image.resize(
                (image.width * 2, image.height * 2),
                Image.Resampling.LANCZOS,
            )

            extracted_text = pytesseract.image_to_string(
                image,
                config="--psm 6",
            )

    except pytesseract.TesseractNotFoundError as error:
        raise RuntimeError(
            "Tesseract OCR is not installed or cannot be found. "
            "Install Tesseract and configure TESSERACT_CMD."
        ) from error

    except Exception as error:
        raise RuntimeError(
            f"Could not extract screen text: {error}"
        ) from error

    return extracted_text.strip()