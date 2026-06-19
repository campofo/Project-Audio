import json
from typing import Dict, Iterable
from urllib import request

from .config import NodeConfig
from .incidents import IncidentRecord
from .sync_state import SyncState


def _post_json(url: str, payload: Dict, device_key: str = "") -> Dict:
    body = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if device_key:
        headers["X-Device-Key"] = device_key
    req = request.Request(
        url,
        data=body,
        headers=headers,
        method="POST",
    )
    with request.urlopen(req, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def register_device(config: NodeConfig, central_api_url: str = "") -> Dict:
    base_url = (central_api_url or config.central_api_url).rstrip("/")
    if not base_url:
        raise ValueError("central_api_url is required to register this device")
    payload = {
        "node_id": config.node_id,
        "latitude": config.location.latitude,
        "longitude": config.location.longitude,
        "status": "online",
        "model_path": config.model_path,
        "labels": config.labels,
        "incident_classes": sorted(config.incident_classes),
        "firmware_version": "audio-node-0.1.0",
        "api_key": config.device_api_key,
    }
    if config.admin_api_key:
        payload["admin_api_key"] = config.admin_api_key
    return _post_json(f"{base_url}/devices/register", payload, device_key=config.device_api_key)


def send_heartbeat(config: NodeConfig, central_api_url: str = "") -> Dict:
    base_url = (central_api_url or config.central_api_url).rstrip("/")
    if not base_url:
        raise ValueError("central_api_url is required to send heartbeat")
    return _post_json(
        f"{base_url}/devices/{config.node_id}/heartbeat",
        {},
        device_key=config.device_api_key,
    )


def sync_incidents(
    records: Iterable[Dict],
    central_api_url: str,
    device_key: str = "",
    sync_state: SyncState = None,
) -> Dict:
    base_url = central_api_url.rstrip("/")
    if not base_url:
        raise ValueError("central_api_url is required to sync incidents")
    records = list(records)
    pending = sync_state.pending_records(records) if sync_state else records
    uploaded = 0
    duplicates = 0
    for record in pending:
        IncidentRecord.from_dict(record)
        response = _post_json(f"{base_url}/ingest/incident", record, device_key=device_key)
        if response.get("accepted"):
            uploaded += 1
            duplicates += 1 if response.get("duplicate") else 0
            if sync_state:
                sync_state.mark_synced(record)
    return {
        "total_local": len(records),
        "attempted": len(pending),
        "uploaded": uploaded,
        "duplicates": duplicates,
        "pending": len(pending) - uploaded,
    }
