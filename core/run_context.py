# core/run_context.py
import os
import datetime

DATA_DIR = "data"
RUN_ID_FILE = os.path.join(DATA_DIR, "current_run_id.txt")

def get_or_create_run_id() -> str:
    """
    Retrieves the active run ID or creates a new one if none exists.
    Persists across app restarts.
    """
    os.makedirs(DATA_DIR, exist_ok=True)

    if os.path.exists(RUN_ID_FILE):
        with open(RUN_ID_FILE, "r") as f:
            content = f.read().strip()
            if content:
                return content

    # Create new run ID based on UTC timestamp
    run_id = f"run_{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    with open(RUN_ID_FILE, "w") as f:
        f.write(run_id)

    return run_id

def clear_run_id():
    """
    Removes the current run ID file. 
    This forces the generation of a NEW run ID on next startup.
    """
    if os.path.exists(RUN_ID_FILE):
        os.remove(RUN_ID_FILE)
