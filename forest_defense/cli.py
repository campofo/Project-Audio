import argparse
import queue

from .audio import AudioRecorder
from .classifier import AudioClassifier
from .config import load_config
from .demo import demo_devices, demo_incidents
from .devices import DeviceRegistry
from .diagnostics import print_diagnostics
from .fleet_store import FleetStore
from .incidents import IncidentLog
from .provisioning import provision_device, provision_fleet
from .sync_state import SyncState
from .uplink import register_device, send_heartbeat, sync_incidents
from .wav_io import read_wav_mono


def run_live(config_path: str) -> None:
    config = load_config(config_path)
    classifier = AudioClassifier.from_config(config)
    recorder = AudioRecorder(
        rate=config.capture_rate,
        record_seconds=config.sample_duration_seconds,
    )
    log = IncidentLog(config.incident_log_path)
    audio_queue = recorder.get_audio_queue()

    try:
        import threading

        recording_thread = threading.Thread(target=recorder.record_audio, daemon=True)
        recording_thread.start()

        while True:
            try:
                audio_data = audio_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            prediction = classifier.classify_audio(
                audio_data,
                source_rate=config.capture_rate,
            )
            print(
                f"{prediction.label} "
                f"confidence={prediction.confidence:.3f} "
                f"verified={prediction.is_verified} "
                f"incident={prediction.is_incident}"
            )
            if prediction.is_incident:
                log.append(log.build_record(config, prediction))
    except KeyboardInterrupt:
        print("\nStopped Forest Defense audio node.")


def classify_file(config_path: str, wav_path: str) -> None:
    config = load_config(config_path)
    classifier = AudioClassifier.from_config(config)
    log = IncidentLog(config.incident_log_path)
    audio, rate = read_wav_mono(wav_path)
    prediction = classifier.classify_audio(audio, source_rate=rate)
    print(
        f"{prediction.label} "
        f"confidence={prediction.confidence:.3f} "
        f"verified={prediction.is_verified} "
        f"incident={prediction.is_incident}"
    )
    if prediction.is_incident:
        log.append(log.build_record(config, prediction))


def seed_demo(config_path: str) -> None:
    config = load_config(config_path)
    log = IncidentLog(config.incident_log_path)
    registry = DeviceRegistry(config.device_registry_path)
    store = FleetStore(config.fleet_db_path)
    count = 0
    device_count = 0
    for device in demo_devices(config):
        registry.upsert(device)
        store.upsert_device(
            device,
            api_key=config.device_api_key if device.node_id == config.node_id else f"demo-key-{device.node_id}",
        )
        device_count += 1
    for record in demo_incidents(config):
        log.append(record)
        store.append_incident(record)
        count += 1
    print(
        f"Seeded {device_count} demo devices into {config.device_registry_path} "
        f"and {count} demo incidents into {config.incident_log_path}"
    )


def register_with_central(config_path: str, central_api_url: str = "") -> None:
    config = load_config(config_path)
    register_device(config, central_api_url=central_api_url)
    print(f"Registered {config.node_id}")


def heartbeat_central(config_path: str, central_api_url: str = "") -> None:
    config = load_config(config_path)
    send_heartbeat(config, central_api_url=central_api_url)
    print(f"Heartbeat sent for {config.node_id}")


def sync_to_central(config_path: str, central_api_url: str = "") -> None:
    config = load_config(config_path)
    target_url = central_api_url or config.central_api_url
    records = IncidentLog(config.incident_log_path).list_records(
        limit=0,
        node_id=config.node_id,
    )
    result = sync_incidents(
        records,
        target_url,
        device_key=config.device_api_key,
        sync_state=SyncState(config.sync_state_path),
    )
    print(
        f"Sync complete for {config.node_id}: "
        f"{result['uploaded']} uploaded, {result['duplicates']} duplicate, "
        f"{result['pending']} pending, {result['total_local']} local"
    )


def sync_status(config_path: str) -> None:
    config = load_config(config_path)
    records = IncidentLog(config.incident_log_path).list_records(
        limit=0,
        node_id=config.node_id,
    )
    summary = SyncState(config.sync_state_path).summary(records)
    print(
        f"Sync status for {config.node_id}: "
        f"{summary['synced']} synced, {summary['pending']} pending, "
        f"{summary['total_local']} local"
    )


def provision_device_command(args) -> None:
    config = load_config(args.config)
    result = provision_device(
        config,
        node_id=args.node_id,
        latitude=args.latitude,
        longitude=args.longitude,
        output_path=args.output,
        device_api_key=args.device_api_key,
        central_api_url=args.central_api_url,
        notes=args.notes,
    )
    print(f"Provisioned {args.node_id}")
    print(f"Config written to {result['output_path']}")
    if not args.device_api_key:
        print("Generated device key stored in the config file.")


def provision_fleet_command(args) -> None:
    config = load_config(args.config)
    results = provision_fleet(
        config,
        manifest_path=args.manifest,
        output_dir=args.output_dir,
        central_api_url=args.central_api_url,
    )
    print(f"Provisioned {len(results)} devices")
    for result in results:
        print(f"- {result['device']['node_id']} -> {result['output_path']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Forest Defense audio field node")
    parser.add_argument(
        "--config",
        default="config/node_config.example.json",
        help="Path to node config JSON",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("live", help="Run live microphone classification")
    classify_parser = subparsers.add_parser("classify-file", help="Classify a WAV file")
    classify_parser.add_argument("wav_path")
    subparsers.add_parser("diagnose", help="Check field-node config and dependencies")
    subparsers.add_parser("seed-demo", help="Write demo incidents for dashboard testing")
    register_parser = subparsers.add_parser("register-device", help="Register this node with a central API")
    register_parser.add_argument("--central-api-url", default="")
    heartbeat_parser = subparsers.add_parser("heartbeat", help="Send a heartbeat to the central API")
    heartbeat_parser.add_argument("--central-api-url", default="")
    sync_parser = subparsers.add_parser("sync-incidents", help="Push local incidents to the central API")
    sync_parser.add_argument("--central-api-url", default="")
    subparsers.add_parser("sync-status", help="Show local incident sync progress")
    provision_parser = subparsers.add_parser("provision-device", help="Provision a new field node config and central registry entry")
    provision_parser.add_argument("--node-id", required=True)
    provision_parser.add_argument("--latitude", required=True, type=float)
    provision_parser.add_argument("--longitude", required=True, type=float)
    provision_parser.add_argument("--output", required=True)
    provision_parser.add_argument("--device-api-key", default="")
    provision_parser.add_argument("--central-api-url", default="")
    provision_parser.add_argument("--notes", default="")
    provision_fleet_parser = subparsers.add_parser(
        "provision-fleet",
        help="Provision many field node configs from a CSV manifest",
    )
    provision_fleet_parser.add_argument("--manifest", required=True)
    provision_fleet_parser.add_argument("--output-dir", required=True)
    provision_fleet_parser.add_argument("--central-api-url", default="")
    args = parser.parse_args()

    if args.command == "classify-file":
        classify_file(args.config, args.wav_path)
    elif args.command == "diagnose":
        print_diagnostics(args.config)
    elif args.command == "seed-demo":
        seed_demo(args.config)
    elif args.command == "register-device":
        register_with_central(args.config, args.central_api_url)
    elif args.command == "heartbeat":
        heartbeat_central(args.config, args.central_api_url)
    elif args.command == "sync-incidents":
        sync_to_central(args.config, args.central_api_url)
    elif args.command == "sync-status":
        sync_status(args.config)
    elif args.command == "provision-device":
        provision_device_command(args)
    elif args.command == "provision-fleet":
        provision_fleet_command(args)
    else:
        run_live(args.config)


if __name__ == "__main__":
    main()
