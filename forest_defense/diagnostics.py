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

PLACEHOLDER_SECRETS = {
    "",
    "change-this-node-secret",
    "change-this-admin-secret",
    "demo-test-key",
    "test-device-key",
    "admin-test-key",
    "replace-with-this-node-secret",
    "replace-with-central-admin-secret",
}


def readiness_issues(config, model_exists: bool) -> list:
    issues = []
    if not model_exists:
        issues.append("model file is missing")
    if not config.central_api_url:
        issues.append("central_api_url is not configured")
    if config.device_api_key in PLACEHOLDER_SECRETS:
        issues.append("device_api_key must be unique and non-placeholder")
    if config.admin_api_key in PLACEHOLDER_SECRETS:
        issues.append("admin_api_key must be unique and non-placeholder")
    if not config.incident_classes:
        issues.append("incident_classes is empty")
    unknown_incident_classes = sorted(set(config.incident_classes).difference(config.labels))
    if unknown_incident_classes:
        issues.append(
            "incident_classes not present in labels: "
            + ", ".join(unknown_incident_classes)
        )
    if config.confidence_threshold <= 0 or config.confidence_threshold > 1:
        issues.append("confidence_threshold must be between 0 and 1")
    if config.sample_duration_seconds <= 0:
        issues.append("sample_duration_seconds must be greater than zero")
    return issues


def collect_diagnostics(config_path: str) -> dict:
    config = load_config(config_path)
    model_exists = Path(config.model_path).exists()
    packages = {
        package: importlib.util.find_spec(package) is not None
        for package in OPTIONAL_PACKAGES
    }
    issues = readiness_issues(config, model_exists)
    return {
        "node_id": config.node_id,
        "config_path": config_path,
        "model_exists": model_exists,
        "incident_log_parent_exists": Path(config.incident_log_path).parent.exists(),
        "sync_state_path": config.sync_state_path,
        "sync_state_parent_exists": Path(config.sync_state_path).parent.exists(),
        "fleet_db_path": config.fleet_db_path,
        "fleet_db_parent_exists": Path(config.fleet_db_path).parent.exists(),
        "central_api_url": config.central_api_url,
        "device_api_key_configured": bool(config.device_api_key),
        "admin_api_key_configured": bool(config.admin_api_key),
        "production_ready": not issues,
        "readiness_issues": issues,
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
    print(f"Admin API key configured: {diagnostics['admin_api_key_configured']}")
    print(
        "Production readiness: "
        + ("ready" if diagnostics["production_ready"] else "blocked")
    )
    for issue in diagnostics["readiness_issues"]:
        print(f"  - {issue}")
    print("Packages:")
    for package, present in diagnostics["packages"].items():
        state = "ok" if present else "missing"
        print(f"  - {package}: {state}")
    print("Labels:", ", ".join(diagnostics["labels"]))
    print("Incident classes:", ", ".join(diagnostics["incident_classes"]))
