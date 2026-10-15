import traceback

print("[1/5] Python started.", flush=True)

try:
    print("[2/5] Importing voice service...", flush=True)

    from server.services.voice_service import listen_once

    print("[3/5] Voice service imported successfully.", flush=True)
    print(
        "[4/5] Loading the model and recording for 8 seconds. "
        "The first run may take longer.",
        flush=True,
    )

    command = listen_once(timeout_seconds=8)

    print("[5/5] Recognized command:", flush=True)
    print(command, flush=True)

except Exception as error:
    print("\nVOICE TEST FAILED:", repr(error), flush=True)
    traceback.print_exc()

input("\nPress Enter to close this test...")