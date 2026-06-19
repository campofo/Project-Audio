import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List

from .incidents import incident_fingerprint


class SyncState:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> Dict:
        if not self.path.exists():
            return {"synced": {}}
        text = self.path.read_text(encoding="utf-8").strip()
        return json.loads(text) if text else {"synced": {}}

    def _write(self, state: Dict) -> None:
        self.path.write_text(
            json.dumps(state, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def is_synced(self, record: Dict) -> bool:
        return incident_fingerprint(record) in self._read().get("synced", {})

    def mark_synced(self, record: Dict) -> None:
        state = self._read()
        state.setdefault("synced", {})[incident_fingerprint(record)] = {
            "node_id": record["node_id"],
            "class_label": record["class_label"],
            "timestamp": record["timestamp"],
            "synced_at": datetime.now(timezone.utc).isoformat(),
        }
        self._write(state)

    def pending_records(self, records: Iterable[Dict]) -> List[Dict]:
        synced = self._read().get("synced", {})
        return [record for record in records if incident_fingerprint(record) not in synced]

    def summary(self, records: Iterable[Dict]) -> Dict:
        records = list(records)
        pending = self.pending_records(records)
        return {
            "total_local": len(records),
            "synced": len(records) - len(pending),
            "pending": len(pending),
        }
