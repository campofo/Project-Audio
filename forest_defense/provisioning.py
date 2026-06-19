import csv
import json
import secrets
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import LocationConfig, NodeConfig
from .devices import DeviceRecord
from .fleet_store import FleetStore


def build_node_config(
    base_config: NodeConfig,
    node_id: str,
    latitude: float,
    longitude: float,
    device_api_key: str,
    central_api_url: str,
) -> dict:
    return {
        "node_id": node_id,
        "location": {
            "latitude": latitude,
            "longitude": longitude,
        },
        "model_path": base_config.model_path,
        "sample_rate": base_config.sample_rate,
        "capture_rate": base_config.capture_rate,
        "sample_duration_seconds": base_config.sample_duration_seconds,
        "confidence_threshold": base_config.confidence_threshold,
        "incident_log_path": "data/incidents.jsonl",
        "sync_state_path": "data/sync_state.json",
        "device_registry_path": "data/devices.json",
        "fleet_db_path": "data/fleet.db",
        "central_api_url": central_api_url or base_config.central_api_url,
        "device_api_key": device_api_key,
        "stale_after_seconds": base_config.stale_after_seconds,
        "offline_after_seconds": base_config.offline_after_seconds,
        "labels": list(base_config.labels),
        "incident_classes": sorted(base_config.incident_classes),
    }


def provision_device(
    base_config: NodeConfig,
    node_id: str,
    latitude: float,
    longitude: float,
    output_path: str,
    device_api_key: Optional[str] = None,
    central_api_url: str = "",
    notes: str = "",
) -> dict:
    key = device_api_key or secrets.token_urlsafe(32)
    store = FleetStore(base_config.fleet_db_path)
    device = DeviceRecord(
        node_id=node_id,
        latitude=latitude,
        longitude=longitude,
        status="provisioned",
        model_path=base_config.model_path,
        labels=list(base_config.labels),
        incident_classes=sorted(base_config.incident_classes),
        last_seen=datetime.now(timezone.utc).isoformat(),
        notes=notes,
    )
    store.upsert_device(device, api_key=key)

    config_payload = build_node_config(
        base_config,
        node_id=node_id,
        latitude=latitude,
        longitude=longitude,
        device_api_key=key,
        central_api_url=central_api_url,
    )
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(config_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "device": asdict(device),
        "output_path": str(destination),
        "device_api_key": key,
    }


def provision_fleet(
    base_config: NodeConfig,
    manifest_path: str,
    output_dir: str,
    central_api_url: str = "",
) -> list:
    results = []
    manifest = Path(manifest_path)
    destination_dir = Path(output_dir)
    with manifest.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        required = {"node_id", "latitude", "longitude"}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(
                "Fleet manifest missing columns: " + ", ".join(sorted(missing))
            )
        for row in reader:
            node_id = str(row["node_id"]).strip()
            if not node_id:
                continue
            output_path = destination_dir / f"{node_id}.json"
            results.append(
                provision_device(
                    base_config,
                    node_id=node_id,
                    latitude=float(row["latitude"]),
                    longitude=float(row["longitude"]),
                    output_path=str(output_path),
                    device_api_key=str(row.get("device_api_key", "")).strip() or None,
                    central_api_url=central_api_url,
                    notes=str(row.get("notes", "")).strip(),
                )
            )
    return results
