# core/event_recorder.py
import json
import os
import datetime
import threading
from typing import Dict, Any, Optional
from core.run_context import get_or_create_run_id

LOG_DIR = "logs"
SCHEMA_VERSION = 1

_lock = threading.Lock()
_recorder = None

class EventRecorder:
    def __init__(self):
        self.run_id = get_or_create_run_id()
        os.makedirs(LOG_DIR, exist_ok=True)
        self.log_path = os.path.join(LOG_DIR, "events.jsonl")

    def record(self, event_type: str, payload: Dict[str, Any], actor: str = "user"):
        """
        Writes a structured, immutable event to the log.
        """
        entry = {
            "schema_version": SCHEMA_VERSION,
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "run_id": self.run_id,
            "event_type": event_type,
            "actor": actor,
            "payload": payload,
        }

        try:
            with _lock:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry) + "\n")
                    f.flush()
                    os.fsync(f.fileno()) # Force write to disk immediately
        except Exception as e:
            # Critical Safety: Never crash the app because logging failed
            print(f"[WARN] Event logging failed: {e}")

def get_event_recorder() -> EventRecorder:
    """Singleton accessor for the recorder."""
    global _recorder
    if _recorder is None:
        _recorder = EventRecorder()
    return _recorder
