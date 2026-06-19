import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, List, Sequence, Set


@dataclass(frozen=True)
class LocationConfig:
    latitude: float
    longitude: float


@dataclass(frozen=True)
class NodeConfig:
    node_id: str
    location: LocationConfig
    model_path: str
    sample_rate: int = 16000
    capture_rate: int = 44100
    sample_duration_seconds: int = 5
    confidence_threshold: float = 0.75
    incident_classes: Set[str] = field(default_factory=set)
    labels: List[str] = field(default_factory=list)
    incident_log_path: str = "data/incidents.jsonl"
    sync_state_path: str = "data/sync_state.json"
    device_registry_path: str = "data/devices.json"
    fleet_db_path: str = "data/fleet.db"
    central_api_url: str = ""
    device_api_key: str = ""
    admin_api_key: str = ""
    stale_after_seconds: int = 300
    offline_after_seconds: int = 900

    @property
    def target_samples(self) -> int:
        return int(self.sample_rate * self.sample_duration_seconds)


def _require_keys(data: dict, keys: Iterable[str], source: Path) -> None:
    missing = [key for key in keys if key not in data]
    if missing:
        names = ", ".join(missing)
        raise ValueError(f"{source} is missing required key(s): {names}")


def _env_or_config(name: str, data: dict, key: str, default: str = "") -> str:
    return os.environ.get(name, str(data.get(key, default)))


def load_config(path: str = "config/node_config.example.json") -> NodeConfig:
    source = Path(path)
    with source.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    _require_keys(
        data,
        ["node_id", "location", "model_path", "confidence_threshold", "labels"],
        source,
    )
    _require_keys(data["location"], ["latitude", "longitude"], source)

    labels = list(data["labels"])
    if not labels:
        raise ValueError(f"{source} must define at least one class label")

    return NodeConfig(
        node_id=_env_or_config("FOREST_DEFENSE_NODE_ID", data, "node_id"),
        location=LocationConfig(
            latitude=float(data["location"]["latitude"]),
            longitude=float(data["location"]["longitude"]),
        ),
        model_path=str(data["model_path"]),
        sample_rate=int(data.get("sample_rate", 16000)),
        capture_rate=int(data.get("capture_rate", 44100)),
        sample_duration_seconds=int(data.get("sample_duration_seconds", 5)),
        confidence_threshold=float(data["confidence_threshold"]),
        incident_classes=set(data.get("incident_classes", [])),
        labels=labels,
        incident_log_path=str(data.get("incident_log_path", "data/incidents.jsonl")),
        sync_state_path=str(data.get("sync_state_path", "data/sync_state.json")),
        device_registry_path=str(data.get("device_registry_path", "data/devices.json")),
        fleet_db_path=str(data.get("fleet_db_path", "data/fleet.db")),
        central_api_url=_env_or_config(
            "FOREST_DEFENSE_CENTRAL_API_URL",
            data,
            "central_api_url",
        ),
        device_api_key=_env_or_config(
            "FOREST_DEFENSE_DEVICE_API_KEY",
            data,
            "device_api_key",
        ),
        admin_api_key=_env_or_config(
            "FOREST_DEFENSE_ADMIN_API_KEY",
            data,
            "admin_api_key",
        ),
        stale_after_seconds=int(data.get("stale_after_seconds", 300)),
        offline_after_seconds=int(data.get("offline_after_seconds", 900)),
    )


def validate_label_count(labels: Sequence[str], output_count: int) -> None:
    if len(labels) != output_count:
        raise ValueError(
            f"Label count ({len(labels)}) must match model output count ({output_count}). "
            "Update the label map so class order matches the trained model."
        )
