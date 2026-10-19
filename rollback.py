import json
import os
from datetime import datetime
from typing import Dict, Any


class ActionStore:
    """Simple JSON-lines action store used to record before/after snapshots for rollback."""
    def __init__(self, path: str = "actions.log"):
        self.path = path
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)

    def record(self, camera: str, before: Dict[str, Any], after: Dict[str, Any], meta: Dict[str, Any] = None):
        entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "camera": camera,
            "before": before,
            "after": after,
        }
        if meta:
            entry.update({"host": meta.get("host"), "username": meta.get("username"), "password": meta.get("password")})
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    def load(self):
        if not os.path.exists(self.path):
            return []
        out = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except Exception:
                    continue
        return out

    def clear(self):
        if os.path.exists(self.path):
            os.remove(self.path)
