
from server.services.screen_service import (
    capture_screen,
    extract_text_from_screen,
)


def main():
    print("Capturing screen...")

    screenshot_path = capture_screen()
    print(f"Screenshot saved at: {screenshot_path}")

    print("\nExtracting visible text...")
    text = extract_text_from_screen(screenshot_path)

    print("\n===== OCR RESULT =====")
    print(text)
    print("======================")

    if text:
        print("\nPASS: Screen capture and OCR returned text.")
    else:
        print(
            "\nCHECK: The screenshot was captured, but no text "
            "was recognized."
        )


if __name__ == "__main__":
    main()
