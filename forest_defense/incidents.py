import json
import hashlib
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .classifier import PredictionResult
from .config import NodeConfig


def incident_fingerprint(record: Dict) -> str:
    fields = {
        "timestamp": record["timestamp"],
        "node_id": record["node_id"],
        "class_label": record["class_label"],
        "class_index": int(record["class_index"]),
        "confidence": round(float(record["confidence"]), 6),
        "latitude": round(float(record["latitude"]), 6),
        "longitude": round(float(record["longitude"]), 6),
    }
    payload = json.dumps(fields, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class IncidentRecord:
    timestamp: str
    node_id: str
    class_label: str
    class_index: int
    confidence: float
    verified: bool
    incident: bool
    latitude: float
    longitude: float
    audio_window_seconds: int
    model_path: str

    @classmethod
    def from_dict(cls, data: Dict) -> "IncidentRecord":
        required = [
            "timestamp",
            "node_id",
            "class_label",
            "class_index",
            "confidence",
            "verified",
            "incident",
            "latitude",
            "longitude",
            "audio_window_seconds",
            "model_path",
        ]
        missing = [key for key in required if key not in data]
        if missing:
            raise ValueError(f"Incident payload missing key(s): {', '.join(missing)}")
        return cls(
            timestamp=str(data["timestamp"]),
            node_id=str(data["node_id"]),
            class_label=str(data["class_label"]),
            class_index=int(data["class_index"]),
            confidence=float(data["confidence"]),
            verified=bool(data["verified"]),
            incident=bool(data["incident"]),
            latitude=float(data["latitude"]),
            longitude=float(data["longitude"]),
            audio_window_seconds=int(data["audio_window_seconds"]),
            model_path=str(data["model_path"]),
        )


class IncidentLog:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def build_record(
        self,
        config: NodeConfig,
        prediction: PredictionResult,
    ) -> IncidentRecord:
        return IncidentRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            node_id=config.node_id,
            class_label=prediction.label,
            class_index=prediction.class_index,
            confidence=prediction.confidence,
            verified=prediction.is_verified,
            incident=prediction.is_incident,
            latitude=config.location.latitude,
            longitude=config.location.longitude,
            audio_window_seconds=config.sample_duration_seconds,
            model_path=config.model_path,
        )

    def append(self, record: IncidentRecord) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(record), sort_keys=True) + "\n")

    def list_records(self, limit: int = 100, node_id: Optional[str] = None) -> List[Dict]:
        if not self.path.exists():
            return []

        lines = self.path.read_text(encoding="utf-8").splitlines()
        records = [json.loads(line) for line in lines if line.strip()]
        if node_id:
            records = [record for record in records if record.get("node_id") == node_id]
        return records[-limit:] if limit else records

    def summary(self, node_id: Optional[str] = None) -> Dict:
        records = self.list_records(limit=0, node_id=node_id)
        by_class: Dict[str, int] = {}
        by_device: Dict[str, int] = {}
        latest: Optional[Dict] = None

        for record in records:
            label = record.get("class_label", "unknown")
            device = record.get("node_id", "unknown")
            by_class[label] = by_class.get(label, 0) + 1
            by_device[device] = by_device.get(device, 0) + 1
            if latest is None or record.get("timestamp", "") > latest.get("timestamp", ""):
                latest = record

        return {
            "total_incidents": len(records),
            "by_class": by_class,
            "by_device": by_device,
            "latest": latest,
        }
