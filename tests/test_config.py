from forest_defense.config import load_config


def test_load_config_allows_environment_secret_overrides(tmp_path, monkeypatch):
    config_path = tmp_path / "node_config.json"
    config_path.write_text(
        """
{
  "node_id": "json-node",
  "location": {"latitude": 9.4, "longitude": -0.8},
  "model_path": "model1_1.h5",
  "confidence_threshold": 0.75,
  "central_api_url": "http://json-central:8000",
  "device_api_key": "json-device-key",
  "admin_api_key": "json-admin-key",
  "labels": ["background", "chainsaw"],
  "incident_classes": ["chainsaw"]
}
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("FOREST_DEFENSE_NODE_ID", "env-node")
    monkeypatch.setenv(
        "FOREST_DEFENSE_CENTRAL_API_URL",
        "http://env-central:8000",
    )
    monkeypatch.setenv("FOREST_DEFENSE_DEVICE_API_KEY", "env-device-key")
    monkeypatch.setenv("FOREST_DEFENSE_ADMIN_API_KEY", "env-admin-key")

    config = load_config(str(config_path))

    assert config.node_id == "env-node"
    assert config.central_api_url == "http://env-central:8000"
    assert config.device_api_key == "env-device-key"
    assert config.admin_api_key == "env-admin-key"
