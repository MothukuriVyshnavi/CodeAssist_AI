
import requests

OLLAMA_API_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen2.5-coder:1.5b"


def ask_ai(prompt: str) -> str:
    """Send a prompt to the local Ollama model."""

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
        "stream": False,
    }

    try:
        response = requests.post(
            OLLAMA_API_URL,
            json=payload,
            timeout=120,
        )
        response.raise_for_status()

        result = response.json()
        return result["message"]["content"]

    except requests.RequestException as error:
        return f"Could not connect to Ollama: {error}"
    except (KeyError, ValueError):
        return "Ollama returned an unexpected response."