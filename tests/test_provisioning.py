import json

from forest_defense.config import LocationConfig, NodeConfig
from forest_defense.fleet_store import FleetStore
from forest_defense.provisioning import provision_device, provision_fleet


def test_provision_device_writes_node_config_and_registry(tmp_path):
    base = NodeConfig(
        node_id="central",
        location=LocationConfig(latitude=9.4, longitude=-0.8),
        model_path="model1_1.h5",
        confidence_threshold=0.75,
        incident_classes={"chainsaw", "gunshot"},
        labels=["background", "chainsaw", "gunshot"],
        fleet_db_path=str(tmp_path / "fleet.db"),
        central_api_url="http://central.local:8000",
        device_api_key="central-key",
        admin_api_key="admin-key",
    )
    output = tmp_path / "nodes" / "fdp-node-010.json"

    result = provision_device(
        base,
        node_id="fdp-node-010",
        latitude=9.52,
        longitude=-0.71,
        output_path=str(output),
        device_api_key="node-010-key",
        notes="Boundary post",
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    device = FleetStore(base.fleet_db_path).get_device("fdp-node-010")
    assert result["device_api_key"] == "node-010-key"
    assert payload["node_id"] == "fdp-node-010"
    assert payload["device_api_key"] == "node-010-key"
    assert payload["central_api_url"] == "http://central.local:8000"
    assert device["notes"] == "Boundary post"
    assert FleetStore(base.fleet_db_path).authorize("fdp-node-010", "node-010-key")


def test_provision_fleet_writes_configs_from_manifest(tmp_path):
    base = NodeConfig(
        node_id="central",
        location=LocationConfig(latitude=9.4, longitude=-0.8),
        model_path="model1_1.h5",
        confidence_threshold=0.75,
        incident_classes={"chainsaw", "gunshot"},
        labels=["background", "chainsaw", "gunshot"],
        fleet_db_path=str(tmp_path / "fleet.db"),
        central_api_url="http://central.local:8000",
        device_api_key="central-key",
        admin_api_key="admin-key",
    )
    manifest = tmp_path / "fleet.csv"
    manifest.write_text(
        "\n".join(
            [
                "node_id,latitude,longitude,device_api_key,notes",
                "fdp-node-011,9.11,-0.61,node-011-key,North ridge",
                "fdp-node-012,9.12,-0.62,,South ridge",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    results = provision_fleet(
        base,
        manifest_path=str(manifest),
        output_dir=str(tmp_path / "nodes"),
        central_api_url="http://forest-command.local:8000",
    )

    store = FleetStore(base.fleet_db_path)
    first_payload = json.loads(
        (tmp_path / "nodes" / "fdp-node-011.json").read_text(encoding="utf-8")
    )
    second_payload = json.loads(
        (tmp_path / "nodes" / "fdp-node-012.json").read_text(encoding="utf-8")
    )
    assert len(results) == 2
    assert first_payload["device_api_key"] == "node-011-key"
    assert first_payload["central_api_url"] == "http://forest-command.local:8000"
    assert second_payload["device_api_key"]
    assert store.get_device("fdp-node-011")["notes"] == "North ridge"
    assert store.get_device("fdp-node-012")["notes"] == "South ridge"
    assert store.authorize("fdp-node-011", "node-011-key")
