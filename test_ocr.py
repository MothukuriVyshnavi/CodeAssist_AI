
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image, ImageDraw, ImageFont

from server.services.screen_service import extract_text_from_screen


def main():
    print("Creating a sample image...")

    sample_code = (
        "def add(a, b):\n"
        "    return a + b"
    )

    with TemporaryDirectory(prefix="codeassist_ocr_test_") as folder:
        image_path = Path(folder) / "ocr_test.png"

        image = Image.new("RGB", (1200, 300), "white")
        draw = ImageDraw.Draw(image)

        # Use a readable monospace font on Windows if available.
        try:
            font = ImageFont.truetype(
                r"C:\Windows\Fonts\consola.ttf",
                36,
            )
        except OSError:
            font = ImageFont.load_default()

        draw.multiline_text(
            (40, 40),
            sample_code,
            fill="black",
            font=font,
            spacing=25,
        )

        image.save(image_path)

        print("Sample image created.")
        print("Testing Tesseract OCR...")

        extracted_text = extract_text_from_screen(
            str(image_path)
        )

        print("\n--- OCR RESULT ---")
        print(extracted_text)
        print("------------------")

        if "def add" in extracted_text and "return" in extracted_text:
            print("\nPASS: Tesseract recognized the sample code.")
        else:
            print(
                "\nCHECK: OCR returned text, but some code may "
                "have been misread. Inspect the result above."
            )


if __name__ == "__main__":
    main()
