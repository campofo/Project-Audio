from pathlib import Path
from tempfile import NamedTemporaryFile
from datetime import datetime, timezone

from .classifier import AudioClassifier
from .config import NodeConfig, load_config
from .devices import DeviceRecord, DeviceRegistry
from .fleet_store import FleetStore
from .incidents import IncidentLog, IncidentRecord
from .wav_io import read_wav_mono

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app(
    config: NodeConfig = None,
    classifier: AudioClassifier = None,
    incident_log: IncidentLog = None,
    device_registry: DeviceRegistry = None,
    fleet_store: FleetStore = None,
):
    from fastapi import FastAPI, File, Header, HTTPException, UploadFile
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    node_config = config or load_config()
    node_classifier = classifier
    store = fleet_store or FleetStore(node_config.fleet_db_path)
    store.register_config(node_config)
    log = incident_log
    registry = device_registry

    def get_classifier():
        nonlocal node_classifier
        if node_classifier is None:
            node_classifier = AudioClassifier.from_config(node_config)
        return node_classifier

    def append_incident(record: IncidentRecord) -> bool:
        inserted = store.append_incident(record)
        if inserted and log:
            log.append(record)
        return inserted

    def build_local_record(prediction) -> IncidentRecord:
        return IncidentRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            node_id=node_config.node_id,
            class_label=prediction.label,
            class_index=prediction.class_index,
            confidence=prediction.confidence,
            verified=prediction.is_verified,
            incident=prediction.is_incident,
            latitude=node_config.location.latitude,
            longitude=node_config.location.longitude,
            audio_window_seconds=node_config.sample_duration_seconds,
            model_path=node_config.model_path,
        )

    def require_device_key(node_id: str, x_device_key: str = "") -> None:
        if not store.authorize(node_id, x_device_key):
            raise HTTPException(status_code=401, detail="Invalid device key")

    def require_admin_key(x_admin_key: str = "") -> None:
        if not node_config.admin_api_key or x_admin_key != node_config.admin_api_key:
            raise HTTPException(status_code=401, detail="Invalid admin key")

    def health_kwargs():
        return {
            "stale_after_seconds": node_config.stale_after_seconds,
            "offline_after_seconds": node_config.offline_after_seconds,
        }

    app = FastAPI(
        title="Forest Defense Audio Node",
        description="Local API for the Forest Defense audio field prototype.",
        version="0.1.0",
    )
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    def dashboard():
        dashboard_path = STATIC_DIR / "dashboard.html"
        if not dashboard_path.exists():
            raise HTTPException(status_code=404, detail="Dashboard assets are missing")
        return FileResponse(dashboard_path)

    @app.get("/health")
    def health():
        return {"status": "ok", "node_id": node_config.node_id}

    @app.get("/status")
    def status():
        return {
            "node_id": node_config.node_id,
            "location": {
                "latitude": node_config.location.latitude,
                "longitude": node_config.location.longitude,
            },
            "model_path": node_config.model_path,
            "confidence_threshold": node_config.confidence_threshold,
            "incident_classes": sorted(node_config.incident_classes),
            "labels": node_config.labels,
            "incident_log_path": node_config.incident_log_path,
            "device_registry_path": node_config.device_registry_path,
            "fleet_db_path": node_config.fleet_db_path,
            "incident_summary": store.summary(),
            "device_count": len(store.list_devices()),
            "device_health": store.health_summary(**health_kwargs()),
            "stale_after_seconds": node_config.stale_after_seconds,
            "offline_after_seconds": node_config.offline_after_seconds,
        }

    @app.get("/incidents")
    def incidents(limit: int = 100, node_id: str = None):
        return {"incidents": store.list_incidents(limit=limit, node_id=node_id)}

    @app.get("/incidents/summary")
    def incident_summary(node_id: str = None):
        return store.summary(node_id=node_id)

    @app.get("/incidents/{incident_id}")
    def incident_detail(incident_id: int):
        record = store.get_incident(incident_id)
        if not record:
            raise HTTPException(status_code=404, detail="Incident not found")
        return {
            "incident": record,
            "events": store.list_incident_events(incident_id),
        }

    @app.get("/incidents/{incident_id}/events")
    def incident_events(incident_id: int):
        if not store.get_incident(incident_id):
            raise HTTPException(status_code=404, detail="Incident not found")
        return {"events": store.list_incident_events(incident_id)}

    @app.post("/incidents/{incident_id}/acknowledge")
    async def acknowledge_incident(
        incident_id: int,
        payload: dict = None,
        x_admin_key: str = Header(default=""),
    ):
        require_admin_key(x_admin_key)
        payload = payload or {}
        operator = str(payload.get("operator", "operator"))
        record = store.update_incident_status(incident_id, "acknowledged", operator)
        if not record:
            raise HTTPException(status_code=404, detail="Incident not found")
        return {"incident": record}

    @app.post("/incidents/{incident_id}/resolve")
    async def resolve_incident(
        incident_id: int,
        payload: dict = None,
        x_admin_key: str = Header(default=""),
    ):
        require_admin_key(x_admin_key)
        payload = payload or {}
        operator = str(payload.get("operator", "operator"))
        notes = str(payload.get("notes", ""))
        record = store.update_incident_status(incident_id, "resolved", operator, notes)
        if not record:
            raise HTTPException(status_code=404, detail="Incident not found")
        return {"incident": record}

    @app.post("/incidents/{incident_id}/reopen")
    async def reopen_incident(
        incident_id: int,
        payload: dict = None,
        x_admin_key: str = Header(default=""),
    ):
        require_admin_key(x_admin_key)
        payload = payload or {}
        operator = str(payload.get("operator", "operator"))
        notes = str(payload.get("notes", ""))
        record = store.update_incident_status(incident_id, "open", operator, notes)
        if not record:
            raise HTTPException(status_code=404, detail="Incident not found")
        return {"incident": record}

    @app.get("/devices")
    def devices():
        return {
            "devices": store.list_devices_with_health(**health_kwargs()),
            "health": store.health_summary(**health_kwargs()),
        }

    @app.get("/devices/{node_id}")
    def device_detail(node_id: str):
        device = store.get_device_with_health(node_id, **health_kwargs())
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        return {
            "device": device,
            "incident_summary": store.summary(node_id=node_id),
            "recent_incidents": store.list_incidents(limit=25, node_id=node_id),
        }

    @app.post("/devices/register")
    async def register_device(
        payload: dict,
        x_device_key: str = Header(default=""),
        x_admin_key: str = Header(default=""),
    ):
        try:
            api_key = str(payload.get("api_key", "")) or x_device_key
            if not api_key:
                raise ValueError("api_key or X-Device-Key header is required")
            device = DeviceRecord(
                node_id=str(payload["node_id"]),
                latitude=float(payload["latitude"]),
                longitude=float(payload["longitude"]),
                status=str(payload.get("status", "online")),
                model_path=str(payload.get("model_path", "")),
                labels=list(payload.get("labels", [])),
                incident_classes=list(payload.get("incident_classes", [])),
                last_seen=str(payload.get("last_seen", ""))
                or datetime.now(timezone.utc).isoformat(),
                firmware_version=str(payload.get("firmware_version", "audio-node-0.1.0")),
                notes=str(payload.get("notes", "")),
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        existing_key = store.get_api_key(device.node_id)
        if existing_key and api_key != existing_key:
            raise HTTPException(status_code=401, detail="Invalid device key")
        if not existing_key:
            require_admin_key(x_admin_key or str(payload.get("admin_api_key", "")))
        store.upsert_device(device, api_key=api_key)
        if registry:
            registry.upsert(device)
        return {"device": device.__dict__}

    @app.post("/devices/{node_id}/rotate-key")
    async def rotate_device_key(
        node_id: str,
        payload: dict = None,
        x_admin_key: str = Header(default=""),
    ):
        require_admin_key(x_admin_key)
        payload = payload or {}
        device = store.rotate_device_key(
            node_id,
            api_key=str(payload.get("device_api_key", "")),
        )
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        return {"device": device, "device_api_key": device["device_api_key"]}

    @app.post("/devices/{node_id}/revoke")
    async def revoke_device(
        node_id: str,
        x_admin_key: str = Header(default=""),
    ):
        require_admin_key(x_admin_key)
        device = store.revoke_device(node_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
        return {"device": device}

    @app.post("/devices/{node_id}/heartbeat")
    def heartbeat(node_id: str, x_device_key: str = Header(default="")):
        require_device_key(node_id, x_device_key)
        device = store.heartbeat(
            node_id,
            location=node_config.location if node_id == node_config.node_id else None,
        )
        return {"device": device.__dict__}

    @app.post("/ingest/incident")
    async def ingest_incident(payload: dict, x_device_key: str = Header(default="")):
        try:
            record = IncidentRecord.from_dict(payload)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        require_device_key(record.node_id, x_device_key)
        inserted = append_incident(record)
        stored_record = store.get_incident_by_record(record) or record.__dict__
        store.heartbeat(
            record.node_id,
            location=type(node_config.location)(
                latitude=record.latitude,
                longitude=record.longitude,
            ),
        )
        return {"accepted": True, "duplicate": not inserted, "record": stored_record}

    @app.post("/classify-file")
    async def classify_file(file: UploadFile = File(...)):
        suffix = Path(file.filename or "audio.wav").suffix or ".wav"
        try:
            with NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
                tmp.write(await file.read())
                tmp.flush()
                audio, rate = read_wav_mono(tmp.name)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        prediction = get_classifier().classify_audio(audio, source_rate=rate)
        record = build_local_record(prediction)
        if prediction.is_incident:
            append_incident(record)
            store.heartbeat(node_config.node_id, location=node_config.location)

        return {
            "label": prediction.label,
            "class_index": prediction.class_index,
            "confidence": prediction.confidence,
            "verified": prediction.is_verified,
            "incident": prediction.is_incident,
            "record": record.__dict__,
        }

    return app


def app():
    return create_app()
