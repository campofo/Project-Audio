import importlib.util
from pathlib import Path

from .config import load_config


OPTIONAL_PACKAGES = [
    "fastapi",
    "librosa",
    "numpy",
    "pyaudio",
    "tensorflow",
    "uvicorn",
]


def collect_diagnostics(config_path: str) -> dict:
    config = load_config(config_path)
    packages = {
        package: importlib.util.find_spec(package) is not None
        for package in OPTIONAL_PACKAGES
    }
    return {
        "node_id": config.node_id,
        "config_path": config_path,
        "model_exists": Path(config.model_path).exists(),
        "incident_log_parent_exists": Path(config.incident_log_path).parent.exists(),
        "sync_state_path": config.sync_state_path,
        "sync_state_parent_exists": Path(config.sync_state_path).parent.exists(),
        "fleet_db_path": config.fleet_db_path,
        "fleet_db_parent_exists": Path(config.fleet_db_path).parent.exists(),
        "central_api_url": config.central_api_url,
        "device_api_key_configured": bool(config.device_api_key),
        "packages": packages,
        "labels": config.labels,
        "incident_classes": sorted(config.incident_classes),
    }


def print_diagnostics(config_path: str) -> None:
    diagnostics = collect_diagnostics(config_path)
    print(f"Node: {diagnostics['node_id']}")
    print(f"Config: {diagnostics['config_path']}")
    print(f"Model file present: {diagnostics['model_exists']}")
    print(f"Incident log directory present: {diagnostics['incident_log_parent_exists']}")
    print(f"Sync state: {diagnostics['sync_state_path']}")
    print(f"Sync state directory present: {diagnostics['sync_state_parent_exists']}")
    print(f"Fleet database: {diagnostics['fleet_db_path']}")
    print(f"Fleet database directory present: {diagnostics['fleet_db_parent_exists']}")
    print(f"Central API URL: {diagnostics['central_api_url'] or 'not configured'}")
    print(f"Device API key configured: {diagnostics['device_api_key_configured']}")
    print("Packages:")
    for package, present in diagnostics["packages"].items():
        state = "ok" if present else "missing"
        print(f"  - {package}: {state}")
    print("Labels:", ", ".join(diagnostics["labels"]))
    print("Incident classes:", ", ".join(diagnostics["incident_classes"]))
