import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .config import LocationConfig, NodeConfig


@dataclass(frozen=True)
class DeviceRecord:
    node_id: str
    latitude: float
    longitude: float
    status: str
    model_path: str
    labels: List[str]
    incident_classes: List[str]
    last_seen: str
    firmware_version: str = "audio-node-0.1.0"
    notes: str = ""


class DeviceRegistry:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read_all(self) -> Dict[str, Dict]:
        if not self.path.exists():
            return {}
        text = self.path.read_text(encoding="utf-8").strip()
        if not text:
            return {}
        return json.loads(text)

    def _write_all(self, devices: Dict[str, Dict]) -> None:
        self.path.write_text(
            json.dumps(devices, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def upsert(self, device: DeviceRecord) -> DeviceRecord:
        devices = self._read_all()
        devices[device.node_id] = asdict(device)
        self._write_all(devices)
        return device

    def register_config(self, config: NodeConfig, status: str = "online") -> DeviceRecord:
        return self.upsert(
            DeviceRecord(
                node_id=config.node_id,
                latitude=config.location.latitude,
                longitude=config.location.longitude,
                status=status,
                model_path=config.model_path,
                labels=list(config.labels),
                incident_classes=sorted(config.incident_classes),
                last_seen=datetime.now(timezone.utc).isoformat(),
            )
        )

    def heartbeat(
        self,
        node_id: str,
        location: Optional[LocationConfig] = None,
        status: str = "online",
    ) -> DeviceRecord:
        devices = self._read_all()
        existing = devices.get(node_id, {})
        latitude = existing.get("latitude", location.latitude if location else 0.0)
        longitude = existing.get("longitude", location.longitude if location else 0.0)
        device = DeviceRecord(
            node_id=node_id,
            latitude=float(latitude),
            longitude=float(longitude),
            status=status,
            model_path=str(existing.get("model_path", "")),
            labels=list(existing.get("labels", [])),
            incident_classes=list(existing.get("incident_classes", [])),
            last_seen=datetime.now(timezone.utc).isoformat(),
            firmware_version=str(existing.get("firmware_version", "audio-node-0.1.0")),
            notes=str(existing.get("notes", "")),
        )
        return self.upsert(device)

    def get(self, node_id: str) -> Optional[Dict]:
        return self._read_all().get(node_id)

    def list_devices(self) -> List[Dict]:
        return sorted(self._read_all().values(), key=lambda item: item["node_id"])

    def ensure_devices(self, devices: Iterable[DeviceRecord]) -> None:
        for device in devices:
            self.upsert(device)
