
from server.services.llm_service import ask_ai

print("Sending request to Ollama...", flush=True)

answer = ask_ai("Explain a Python function in two simple sentences.")

print("\nAI Response:", flush=True)
print(answer, flush=True)