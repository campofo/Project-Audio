from forest_defense.sync_state import SyncState
from forest_defense.uplink import sync_incidents
from forest_defense.incidents import IncidentLog, IncidentRecord
from forest_defense.config import LocationConfig, NodeConfig


def make_record(label="chainsaw"):
    return {
        "timestamp": "2026-06-15T12:00:00+00:00",
        "node_id": "fdp-node-001",
        "class_label": label,
        "class_index": 1,
        "confidence": 0.91,
        "verified": True,
        "incident": True,
        "latitude": 9.4,
        "longitude": -0.8,
        "audio_window_seconds": 5,
        "model_path": "model1_1.h5",
    }


def test_sync_state_tracks_pending_and_synced_records(tmp_path):
    state = SyncState(str(tmp_path / "sync_state.json"))
    records = [make_record()]

    assert state.summary(records) == {"total_local": 1, "synced": 0, "pending": 1}
    state.mark_synced(records[0])

    assert state.is_synced(records[0]) is True
    assert state.pending_records(records) == []
    assert state.summary(records) == {"total_local": 1, "synced": 1, "pending": 0}


def test_sync_incidents_skips_previously_synced_records(monkeypatch, tmp_path):
    state = SyncState(str(tmp_path / "sync_state.json"))
    records = [make_record("chainsaw"), make_record("gunshot")]
    state.mark_synced(records[0])
    sent = []

    def fake_post(url, payload, device_key=""):
        sent.append(payload)
        return {"accepted": True, "duplicate": False}

    monkeypatch.setattr("forest_defense.uplink._post_json", fake_post)
    result = sync_incidents(
        records,
        "http://central.example",
        device_key="secret",
        sync_state=state,
    )

    assert sent == [records[1]]
    assert result == {
        "total_local": 2,
        "attempted": 1,
        "uploaded": 1,
        "duplicates": 0,
        "pending": 0,
    }
    assert state.summary(records) == {"total_local": 2, "synced": 2, "pending": 0}


def test_incident_log_filters_records_by_node_before_sync(tmp_path):
    config = NodeConfig(
        node_id="fdp-node-001",
        location=LocationConfig(latitude=9.4, longitude=-0.8),
        model_path="model1_1.h5",
        confidence_threshold=0.75,
        labels=["background", "chainsaw"],
        incident_log_path=str(tmp_path / "incidents.jsonl"),
        sync_state_path=str(tmp_path / "sync_state.json"),
        device_api_key="key-001",
    )
    log = IncidentLog(config.incident_log_path)
    own_record = IncidentRecord.from_dict(make_record("chainsaw"))
    other_data = make_record("gunshot")
    other_data["node_id"] = "fdp-node-002"
    log.append(own_record)
    log.append(IncidentRecord.from_dict(other_data))

    records = log.list_records(limit=0, node_id=config.node_id)

    assert len(records) == 1
    assert records[0]["node_id"] == "fdp-node-001"
