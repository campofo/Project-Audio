from datetime import datetime, timedelta, timezone

from .devices import DeviceRecord
from .incidents import IncidentRecord


def demo_devices(config):
    now = datetime.now(timezone.utc)
    examples = [
        (config.node_id, config.location.latitude, config.location.longitude, "online", ""),
        ("fdp-audio-node-002", 9.5102, -0.7344, "online", "Near reserve boundary"),
        ("fdp-audio-node-003", 9.2868, -0.9821, "online", "Community fire volunteer post"),
    ]
    for node_id, latitude, longitude, status, notes in examples:
        yield DeviceRecord(
            node_id=node_id,
            latitude=latitude,
            longitude=longitude,
            status=status,
            model_path=config.model_path,
            labels=list(config.labels),
            incident_classes=sorted(config.incident_classes),
            last_seen=(now - timedelta(minutes=2 if node_id != config.node_id else 0)).isoformat(),
            notes=notes,
        )


def demo_incidents(config):
    now = datetime.now(timezone.utc)
    examples = [
        (config.node_id, config.location.latitude, config.location.longitude, "chainsaw", 1, 0.92, now - timedelta(minutes=21)),
        ("fdp-audio-node-002", 9.5102, -0.7344, "gunshot", 2, 0.87, now - timedelta(minutes=12)),
        ("fdp-audio-node-003", 9.2868, -0.9821, "fire_crackling", 3, 0.81, now - timedelta(minutes=4)),
    ]
    for node_id, latitude, longitude, label, index, confidence, timestamp in examples:
        yield IncidentRecord(
            timestamp=timestamp.isoformat(),
            node_id=node_id,
            class_label=label,
            class_index=index,
            confidence=confidence,
            verified=True,
            incident=True,
            latitude=latitude,
            longitude=longitude,
            audio_window_seconds=config.sample_duration_seconds,
            model_path=config.model_path,
        )
