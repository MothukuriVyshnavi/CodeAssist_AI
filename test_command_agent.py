
print("Command Agent test started!", flush=True)

from server.agents.command_agent import understand_command

print("Agent imported successfully!", flush=True)

result = understand_command("Explain a Python function")

print("Agent result:", result, flush=True)