
import os
import tempfile
import wave
from functools import lru_cache
from pathlib import Path

import sounddevice as sd
from faster_whisper import WhisperModel


SAMPLE_RATE = 16000
DEFAULT_MODEL = "base.en"

@lru_cache(maxsize=1)
def load_whisper_model():
    """Load the local Whisper model once and reuse it."""

    model_name = os.getenv(
        "CODEASSIST_WHISPER_MODEL",
        DEFAULT_MODEL,
    )

    print(
        f"Loading faster-whisper model: {model_name}",
        flush=True,
    )
    print(
        "The first run may download the model. Please wait...",
        flush=True,
    )

    try:
        model = WhisperModel(
            model_name,
            device="cpu",
            compute_type="int8",
            cpu_threads=4,
            num_workers=1,
        )

        print("Whisper model loaded successfully.", flush=True)
        return model

    except Exception as error:
        raise RuntimeError(
            f"Could not load faster-whisper model '{model_name}'. "
            "Check your internet connection, disk space, and "
            f"model cache. Details: {error}"
        ) from error

def listen_once(timeout_seconds: int = 8) -> str:
    """
    Record microphone audio for up to timeout_seconds
    and transcribe it using faster-whisper.
    """

    if timeout_seconds <= 0:
        raise ValueError("Recording duration must be positive.")

    try:
        model = load_whisper_model()
        print(
            f"Recording from microphone for {timeout_seconds} seconds...",
            flush=True,
        )
        # Record mono audio at 16 kHz.
        audio = sd.rec(
            int(SAMPLE_RATE * timeout_seconds),
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="int16",
        )
        sd.wait()
        print("Recording finished. Transcribing audio...", flush=True)
        # Save a temporary WAV file for transcription.
        with tempfile.TemporaryDirectory(
            prefix="codeassist_audio_"
        ) as temp_dir:
            audio_path = Path(temp_dir) / "command.wav"

            with wave.open(str(audio_path), "wb") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(SAMPLE_RATE)
                wav_file.writeframes(audio.tobytes())

            # English-only model: specify English.
            # Multilingual model: let Whisper detect the language.
            model_name = os.getenv(
                "CODEASSIST_WHISPER_MODEL",
                DEFAULT_MODEL,
            )

            language = (
                "en"
                if model_name.lower().endswith(".en")
                else None
            )

            segments, info = model.transcribe(
                str(audio_path),
                language=language,
                beam_size=3,
                vad_filter=True,
                vad_parameters={
                    "min_silence_duration_ms": 300,
                },
                condition_on_previous_text=False,
            )

            # Transcription is processed when the generator is consumed.
            text = " ".join(
                segment.text.strip()
                for segment in segments
            ).strip()

            if not text:
                raise RuntimeError(
                    "No speech was recognized. Check your microphone "
                    "and try again."
                )

            return text

    except RuntimeError:
        raise

    except Exception as error:
        raise RuntimeError(
            "Voice recognition failed. Check microphone permissions, "
            "the recording device, and the Whisper installation.\n"
            f"Details: {error}"
        ) from error
