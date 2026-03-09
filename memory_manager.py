import json
import os
import time
from typing import Any, Dict


class SessionMemoryManager:
    def __init__(self, session_dir: str):
        self.session_dir = session_dir
        self.session_file = os.path.join(session_dir, "session-memory.json")
        os.makedirs(self.session_dir, exist_ok=True)

    def load(self) -> Dict[str, Any]:
        if not os.path.exists(self.session_file):
            return {}

        try:
            with open(self.session_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
            return {}
        except Exception:
            return {}

    def save(self, payload: Dict[str, Any]) -> None:
        safe_payload = dict(payload)
        safe_payload["saved_at"] = int(time.time())
        with open(self.session_file, "w", encoding="utf-8") as f:
            json.dump(safe_payload, f, indent=2)
