
def speak(text: str) -> bool:
    """Speak a message using the computer's text-to-speech engine."""

    engine = None

    try:
        import pyttsx3

        engine = pyttsx3.init()
        engine.setProperty("rate", 175)
        engine.say(text)
        engine.runAndWait()

        return True

    except Exception as error:
        print(f"Text-to-speech error: {error}")
        return False

    finally:
        if engine is not None:
            try:
                engine.stop()
            except Exception:
                pass
