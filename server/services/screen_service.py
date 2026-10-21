
import os
import tempfile
from datetime import datetime
from pathlib import Path

import pytesseract

pytesseract.pytesseract.tesseract_cmd = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe"
)

from mss import MSS
from PIL import Image, ImageOps, ImageFilter


# Approximate code-editor area for your 1920x1080 Cursor layout.
# Format: left, top, right, bottom as proportions of the screen.
# Adjust these values if the editor is positioned differently.
EDITOR_CROP = (0.17, 0.08, 0.99, 0.73)


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

    print(f"[Screen] Screenshot saved: {screenshot_path}", flush=True)
    print(
        f"[Screen] Screenshot dimensions: "
        f"{image.width}x{image.height}",
        flush=True,
    )

    return str(screenshot_path)


def configure_tesseract() -> None:
    """Configure the Tesseract executable."""

    configured_path = os.getenv("TESSERACT_CMD")

    if configured_path:
        pytesseract.pytesseract.tesseract_cmd = configured_path
        return

    default_path = Path(
        r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    )

    if default_path.exists():
        pytesseract.pytesseract.tesseract_cmd = str(default_path)


def crop_editor_area(image: Image.Image) -> Image.Image:
    """Crop the approximate code-editor area."""

    crop_setting = os.getenv(
        "CODEASSIST_OCR_CROP", "editor"
    ).lower()

    if crop_setting == "full":
        print("[OCR] Using the full screenshot.", flush=True)
        return image.copy()

    left_ratio, top_ratio, right_ratio, bottom_ratio = EDITOR_CROP
    width, height = image.size

    left = int(width * left_ratio)
    top = int(height * top_ratio)
    right = int(width * right_ratio)
    bottom = int(height * bottom_ratio)

    left = max(0, min(left, width - 1))
    top = max(0, min(top, height - 1))
    right = max(left + 1, min(right, width))
    bottom = max(top + 1, min(bottom, height))

    cropped = image.crop((left, top, right, bottom))

    print(
        f"[OCR] Cropped editor area: "
        f"{cropped.width}x{cropped.height}",
        flush=True,
    )

    return cropped


def preprocess_for_code(image: Image.Image) -> Image.Image:
    """Improve contrast and readability of code text."""

    # Convert to grayscale.
    image = ImageOps.grayscale(image)

    # Improve contrast.
    image = ImageOps.autocontrast(image)

    # Enlarge small editor text.
    image = image.resize(
        (image.width * 3, image.height * 3),
        Image.Resampling.LANCZOS,
    )

    # Sharpen character edges.
    image = image.filter(ImageFilter.SHARPEN)

    return image


def extract_text_from_screen(screenshot_path: str) -> str:
    """Extract visible editor text using Tesseract OCR."""

    configure_tesseract()

    try:
        with Image.open(screenshot_path) as original:
            image = original.convert("RGB")
            image = crop_editor_area(image)
            image = preprocess_for_code(image)

            extracted_text = pytesseract.image_to_string(
                image,
                lang="eng",
                config=(
                    "--oem 3 --psm 6 "
                    "-c preserve_interword_spaces=1 "
                    "-c load_system_dawg=0 "
                    "-c load_freq_dawg=0"
                ),
            )

    except pytesseract.TesseractNotFoundError as error:
        raise RuntimeError(
            "Tesseract OCR was not found. Check the installation "
            "or set the TESSERACT_CMD environment variable."
        ) from error

    except Exception as error:
        raise RuntimeError(
            f"Could not extract screen text: {error}"
        ) from error

    extracted_text = extracted_text.strip()

    print(
        f"[OCR] Extracted {len(extracted_text)} characters.",
        flush=True,
    )

    if extracted_text:
        print("[OCR] Extracted text preview:", flush=True)
        print(extracted_text[:1500], flush=True)
    else:
        print("[OCR] No text was detected.", flush=True)

    return extracted_text
