from pathlib import Path

from forest_defense.config import load_config
from forest_defense.demo import demo_incidents
from forest_defense.diagnostics import collect_diagnostics
from forest_defense.incidents import IncidentLog


def write_config(tmp_path):
    config_path = tmp_path / "node_config.json"
    model_path = tmp_path / "model1_1.h5"
    model_path.write_bytes(b"placeholder")
    config_path.write_text(
        """
{
  "node_id": "fdp-test-node",
  "location": {"latitude": 9.4, "longitude": -0.8},
  "model_path": "%s",
  "sample_rate": 16000,
  "capture_rate": 44100,
  "sample_duration_seconds": 5,
  "confidence_threshold": 0.75,
  "incident_log_path": "%s",
  "device_registry_path": "%s",
  "fleet_db_path": "%s",
  "device_api_key": "demo-test-key",
  "labels": ["background", "chainsaw", "gunshot", "fire_crackling"],
  "incident_classes": ["chainsaw", "gunshot", "fire_crackling"]
}
"""
        % (
            model_path,
            tmp_path / "incidents.jsonl",
            tmp_path / "devices.json",
            tmp_path / "fleet.db",
        ),
        encoding="utf-8",
    )
    return config_path


def test_demo_incidents_are_loggable(tmp_path):
    config = load_config(str(write_config(tmp_path)))
    log = IncidentLog(config.incident_log_path)

    for record in demo_incidents(config):
        log.append(record)

    summary = log.summary()
    assert summary["total_incidents"] == 3
    assert summary["by_class"]["chainsaw"] == 1
    assert summary["by_class"]["gunshot"] == 1
    assert summary["by_class"]["fire_crackling"] == 1


def test_diagnostics_reports_config_and_model_state(tmp_path):
    config_path = write_config(tmp_path)

    diagnostics = collect_diagnostics(str(config_path))

    assert diagnostics["node_id"] == "fdp-test-node"
    assert diagnostics["model_exists"] is True
    assert diagnostics["packages"]["numpy"] is True
    assert Path(diagnostics["config_path"]) == config_path
