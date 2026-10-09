
from server.services.llm_service import ask_ai


def process_command(command: str) -> str:
    """Send the user's programming command to the local AI model."""

    prompt = f"""
You are CodeAssist AI, a personal programming assistant.

Understand the user's programming request and provide a
clear, beginner-friendly response.

User's command:
{command}
"""

    return ask_ai(prompt)