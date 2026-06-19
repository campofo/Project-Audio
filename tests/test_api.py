import io
import wave

import numpy as np
from fastapi.testclient import TestClient

from forest_defense.api import create_app
from forest_defense.classifier import PredictionResult
from forest_defense.config import LocationConfig, NodeConfig
from forest_defense.incidents import IncidentLog


class StubClassifier:
    def classify_audio(self, audio, source_rate):
        return PredictionResult(
            label="chainsaw",
            class_index=1,
            confidence=0.91,
            probabilities=[0.04, 0.91, 0.05],
            is_incident=True,
            is_verified=True,
        )


def make_wav_bytes():
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(16000)
        samples = (np.zeros(1600, dtype=np.int16)).tobytes()
        handle.writeframes(samples)
    buffer.seek(0)
    return buffer.read()


def make_config(tmp_path):
    return NodeConfig(
        node_id="fdp-api-node",
        location=LocationConfig(latitude=9.4, longitude=-0.8),
        model_path="model1_1.h5",
        confidence_threshold=0.75,
        incident_classes={"chainsaw"},
        labels=["background", "chainsaw", "gunshot"],
        incident_log_path=str(tmp_path / "api-incidents.jsonl"),
        device_registry_path=str(tmp_path / "devices.json"),
        fleet_db_path=str(tmp_path / "fleet.db"),
        device_api_key="local-test-key",
        admin_api_key="admin-test-key",
    )


def test_health_and_incidents_endpoints(tmp_path):
    config = make_config(tmp_path)
    app = create_app(
        config=config,
        classifier=StubClassifier(),
        incident_log=IncidentLog(config.incident_log_path),
    )
    client = TestClient(app)

    assert client.get("/health").json() == {"status": "ok", "node_id": "fdp-api-node"}
    devices = client.get("/devices").json()["devices"]
    assert devices[0]["node_id"] == "fdp-api-node"
    device_response = client.get("/devices").json()
    assert device_response["health"]["online"] == 1
    assert device_response["devices"][0]["health"] == "online"
    assert client.get("/incidents").json() == {"incidents": []}
    assert client.get("/incidents/summary").json()["total_incidents"] == 0
    assert client.get("/").status_code == 200


def test_classify_file_logs_incident(tmp_path):
    config = make_config(tmp_path)
    log = IncidentLog(config.incident_log_path)
    app = create_app(config=config, classifier=StubClassifier(), incident_log=log)
    client = TestClient(app)

    response = client.post(
        "/classify-file",
        files={"file": ("sample.wav", make_wav_bytes(), "audio/wav")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["label"] == "chainsaw"
    assert body["incident"] is True
    assert client.get("/incidents").json()["incidents"][0]["class_label"] == "chainsaw"
    summary = client.get("/incidents/summary").json()
    assert summary["total_incidents"] == 1
    assert summary["by_class"] == {"chainsaw": 1}
    assert summary["by_device"] == {"fdp-api-node": 1}


def test_register_remote_device_and_ingest_incident(tmp_path):
    config = make_config(tmp_path)
    log = IncidentLog(config.incident_log_path)
    app = create_app(config=config, classifier=StubClassifier(), incident_log=log)
    client = TestClient(app)

    register_response = client.post(
        "/devices/register",
        json={
            "node_id": "fdp-remote-node",
            "latitude": 9.51,
            "longitude": -0.73,
            "status": "online",
            "model_path": "model1_1.h5",
            "labels": ["background", "chainsaw", "gunshot"],
            "incident_classes": ["chainsaw", "gunshot"],
            "api_key": "remote-test-key",
        },
        headers={"X-Admin-Key": "admin-test-key"},
    )
    assert register_response.status_code == 200
    device_events = client.get("/devices/fdp-remote-node/events").json()["events"]
    assert [event["event_type"] for event in device_events] == ["registered"]

    incident = {
        "timestamp": "2026-06-15T12:00:00+00:00",
        "node_id": "fdp-remote-node",
        "class_label": "gunshot",
        "class_index": 2,
        "confidence": 0.88,
        "verified": True,
        "incident": True,
        "latitude": 9.51,
        "longitude": -0.73,
        "audio_window_seconds": 5,
        "model_path": "model1_1.h5",
    }
    denied_response = client.post("/ingest/incident", json=incident)
    assert denied_response.status_code == 401

    ingest_response = client.post(
        "/ingest/incident",
        json=incident,
        headers={"X-Device-Key": "remote-test-key"},
    )

    assert ingest_response.status_code == 200
    assert ingest_response.json()["duplicate"] is False
    incident_id = ingest_response.json()["record"]["id"]
    created_events = client.get(f"/incidents/{incident_id}/events").json()["events"]
    assert [event["event_type"] for event in created_events] == ["created"]
    duplicate_response = client.post(
        "/ingest/incident",
        json=incident,
        headers={"X-Device-Key": "remote-test-key"},
    )
    assert duplicate_response.status_code == 200
    assert duplicate_response.json()["duplicate"] is True
    assert client.get("/devices/fdp-remote-node").json()["incident_summary"]["total_incidents"] == 1
    filtered = client.get("/incidents?node_id=fdp-remote-node").json()["incidents"]
    assert len(filtered) == 1
    assert filtered[0]["node_id"] == incident["node_id"]
    assert filtered[0]["class_label"] == incident["class_label"]
    assert filtered[0]["status"] == "open"
    summary = client.get("/incidents/summary").json()
    assert summary["by_device"]["fdp-remote-node"] == 1

    denied_ack = client.post(f"/incidents/{incident_id}/acknowledge", json={"operator": "FSD"})
    assert denied_ack.status_code == 401
    ack = client.post(
        f"/incidents/{incident_id}/acknowledge",
        json={"operator": "FSD"},
        headers={"X-Admin-Key": "admin-test-key"},
    )
    assert ack.status_code == 200
    assert ack.json()["incident"]["status"] == "acknowledged"
    detail = client.get(f"/incidents/{incident_id}").json()
    assert detail["incident"]["id"] == incident_id
    assert [event["event_type"] for event in detail["events"]] == [
        "created",
        "acknowledged",
    ]
    resolved = client.post(
        f"/incidents/{incident_id}/resolve",
        json={"operator": "GNFS", "notes": "Response dispatched"},
        headers={"X-Admin-Key": "admin-test-key"},
    )
    assert resolved.status_code == 200
    assert resolved.json()["incident"]["status"] == "resolved"
    events = client.get(f"/incidents/{incident_id}/events").json()["events"]
    assert [event["event_type"] for event in events] == [
        "created",
        "acknowledged",
        "resolved",
    ]
    assert events[-1]["operator"] == "GNFS"
    assert events[-1]["notes"] == "Response dispatched"
    reopened = client.post(
        f"/incidents/{incident_id}/reopen",
        json={"operator": "FSD", "notes": "Follow-up patrol requested"},
        headers={"X-Admin-Key": "admin-test-key"},
    )
    assert reopened.status_code == 200
    assert reopened.json()["incident"]["status"] == "open"
    events = client.get(f"/incidents/{incident_id}/events").json()["events"]
    assert [event["event_type"] for event in events] == [
        "created",
        "acknowledged",
        "resolved",
        "reopened",
    ]
    assert events[-1]["operator"] == "FSD"
    assert events[-1]["notes"] == "Follow-up patrol requested"

    denied_rotation = client.post(
        "/devices/fdp-remote-node/rotate-key",
        json={"device_api_key": "rotated-remote-key"},
    )
    assert denied_rotation.status_code == 401
    rotated = client.post(
        "/devices/fdp-remote-node/rotate-key",
        json={"device_api_key": "rotated-remote-key"},
        headers={"X-Admin-Key": "admin-test-key"},
    )
    assert rotated.status_code == 200
    assert rotated.json()["device_api_key"] == "rotated-remote-key"
    old_key_heartbeat = client.post(
        "/devices/fdp-remote-node/heartbeat",
        headers={"X-Device-Key": "remote-test-key"},
    )
    assert old_key_heartbeat.status_code == 401
    new_key_heartbeat = client.post(
        "/devices/fdp-remote-node/heartbeat",
        headers={"X-Device-Key": "rotated-remote-key"},
    )
    assert new_key_heartbeat.status_code == 200

    revoked = client.post(
        "/devices/fdp-remote-node/revoke",
        headers={"X-Admin-Key": "admin-test-key"},
    )
    assert revoked.status_code == 200
    assert revoked.json()["device"]["status"] == "revoked"
    revoked_heartbeat = client.post(
        "/devices/fdp-remote-node/heartbeat",
        headers={"X-Device-Key": "rotated-remote-key"},
    )
    assert revoked_heartbeat.status_code == 401
    device_detail = client.get("/devices/fdp-remote-node").json()
    assert [event["event_type"] for event in device_detail["events"]] == [
        "registered",
        "key_rotated",
        "revoked",
    ]
    device_events = client.get("/devices/fdp-remote-node/events").json()["events"]
    assert device_events == device_detail["events"]


def test_new_device_registration_requires_admin_key(tmp_path):
    config = make_config(tmp_path)
    app = create_app(config=config, classifier=StubClassifier())
    client = TestClient(app)

    response = client.post(
        "/devices/register",
        json={
            "node_id": "fdp-new-node",
            "latitude": 9.51,
            "longitude": -0.73,
            "model_path": "model1_1.h5",
            "labels": ["background", "chainsaw"],
            "incident_classes": ["chainsaw"],
            "api_key": "new-node-key",
        },
    )

    assert response.status_code == 401
