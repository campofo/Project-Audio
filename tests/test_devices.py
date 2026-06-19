from datetime import datetime, timedelta, timezone

from forest_defense.config import LocationConfig, NodeConfig
from forest_defense.devices import DeviceRecord, DeviceRegistry
from forest_defense.fleet_store import FleetStore
from forest_defense.incidents import IncidentRecord


def make_config(tmp_path, node_id="fdp-node-001"):
    return NodeConfig(
        node_id=node_id,
        location=LocationConfig(latitude=9.4, longitude=-0.8),
        model_path="model1_1.h5",
        confidence_threshold=0.75,
        incident_classes={"chainsaw", "gunshot"},
        labels=["background", "chainsaw", "gunshot"],
        incident_log_path=str(tmp_path / "incidents.jsonl"),
        device_registry_path=str(tmp_path / "devices.json"),
        fleet_db_path=str(tmp_path / "fleet.db"),
        device_api_key="test-device-key",
        admin_api_key="admin-test-key",
    )


def test_device_registry_registers_and_heartbeats_nodes(tmp_path):
    config = make_config(tmp_path)
    registry = DeviceRegistry(config.device_registry_path)

    registry.register_config(config)
    heartbeat = registry.heartbeat(config.node_id, location=config.location)

    devices = registry.list_devices()
    assert len(devices) == 1
    assert devices[0]["node_id"] == "fdp-node-001"
    assert devices[0]["status"] == "online"
    assert heartbeat.node_id == "fdp-node-001"


def test_fleet_store_persists_devices_auth_and_incidents(tmp_path):
    config = make_config(tmp_path)
    store = FleetStore(config.fleet_db_path)

    store.register_config(config)
    assert store.authorize("fdp-node-001", "test-device-key") is True
    assert store.authorize("fdp-node-001", "wrong") is False

    record = IncidentRecord(
        timestamp="2026-06-15T12:00:00+00:00",
        node_id="fdp-node-001",
        class_label="chainsaw",
        class_index=1,
        confidence=0.91,
        verified=True,
        incident=True,
        latitude=9.4,
        longitude=-0.8,
        audio_window_seconds=5,
        model_path="model1_1.h5",
    )
    store.append_incident(record)
    store.append_incident(record)

    assert store.list_devices()[0]["node_id"] == "fdp-node-001"
    stored = store.list_incidents()
    assert len(stored) == 1
    assert stored[0]["class_label"] == "chainsaw"
    assert stored[0]["status"] == "open"
    events = store.list_incident_events(stored[0]["id"])
    assert len(events) == 1
    assert events[0]["event_type"] == "created"
    assert events[0]["operator"] == "device"
    assert store.summary()["by_device"] == {"fdp-node-001": 1}
    assert store.summary()["by_status"] == {"open": 1}

    updated = store.update_incident_status(stored[0]["id"], "acknowledged", "FSD")
    assert updated["status"] == "acknowledged"
    assert updated["acknowledged_by"] == "FSD"
    resolved = store.update_incident_status(stored[0]["id"], "resolved", "GNFS", "Handled")
    assert resolved["status"] == "resolved"
    assert resolved["resolution_notes"] == "Handled"
    events = store.list_incident_events(stored[0]["id"])
    assert [event["event_type"] for event in events] == [
        "created",
        "acknowledged",
        "resolved",
    ]
    assert events[-1]["operator"] == "GNFS"
    assert events[-1]["notes"] == "Handled"


def test_fleet_store_computes_online_stale_and_offline_health(tmp_path):
    store = FleetStore(str(tmp_path / "fleet.db"))
    now = datetime.now(timezone.utc)
    devices = [
        DeviceRecord(
            node_id="online-node",
            latitude=1.0,
            longitude=1.0,
            status="online",
            model_path="model.h5",
            labels=[],
            incident_classes=[],
            last_seen=(now - timedelta(seconds=60)).isoformat(),
        ),
        DeviceRecord(
            node_id="stale-node",
            latitude=1.0,
            longitude=1.0,
            status="online",
            model_path="model.h5",
            labels=[],
            incident_classes=[],
            last_seen=(now - timedelta(seconds=600)).isoformat(),
        ),
        DeviceRecord(
            node_id="offline-node",
            latitude=1.0,
            longitude=1.0,
            status="online",
            model_path="model.h5",
            labels=[],
            incident_classes=[],
            last_seen=(now - timedelta(seconds=1200)).isoformat(),
        ),
    ]
    for device in devices:
        store.upsert_device(device, api_key=f"key-{device.node_id}")

    enriched = {
        device["node_id"]: device["health"]
        for device in store.list_devices_with_health(
            stale_after_seconds=300,
            offline_after_seconds=900,
        )
    }

    assert enriched == {
        "offline-node": "offline",
        "online-node": "online",
        "stale-node": "stale",
    }
