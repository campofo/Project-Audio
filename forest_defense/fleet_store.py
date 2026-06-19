import json
import secrets
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .config import LocationConfig, NodeConfig
from .devices import DeviceRecord
from .incidents import IncidentRecord


class FleetStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS devices (
                    node_id TEXT PRIMARY KEY,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    status TEXT NOT NULL,
                    model_path TEXT NOT NULL,
                    labels_json TEXT NOT NULL,
                    incident_classes_json TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    firmware_version TEXT NOT NULL,
                    notes TEXT NOT NULL,
                    api_key TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS incidents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    class_label TEXT NOT NULL,
                    class_index INTEGER NOT NULL,
                    confidence REAL NOT NULL,
                    verified INTEGER NOT NULL,
                    incident INTEGER NOT NULL,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    audio_window_seconds INTEGER NOT NULL,
                    model_path TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'open',
                    acknowledged_at TEXT NOT NULL DEFAULT '',
                    acknowledged_by TEXT NOT NULL DEFAULT '',
                    resolved_at TEXT NOT NULL DEFAULT '',
                    resolved_by TEXT NOT NULL DEFAULT '',
                    resolution_notes TEXT NOT NULL DEFAULT '',
                    UNIQUE(timestamp, node_id, class_label, class_index, confidence)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS incident_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    operator TEXT NOT NULL,
                    notes TEXT NOT NULL,
                    FOREIGN KEY(incident_id) REFERENCES incidents(id)
                )
                """
            )
            self._ensure_incident_columns(connection)
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_incidents_node_time ON incidents(node_id, timestamp)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status)"
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_incident_events_incident_time
                ON incident_events(incident_id, timestamp)
                """
            )
            self._backfill_incident_events(connection)

    def _ensure_incident_columns(self, connection) -> None:
        existing = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(incidents)").fetchall()
        }
        columns = {
            "status": "TEXT NOT NULL DEFAULT 'open'",
            "acknowledged_at": "TEXT NOT NULL DEFAULT ''",
            "acknowledged_by": "TEXT NOT NULL DEFAULT ''",
            "resolved_at": "TEXT NOT NULL DEFAULT ''",
            "resolved_by": "TEXT NOT NULL DEFAULT ''",
            "resolution_notes": "TEXT NOT NULL DEFAULT ''",
        }
        for name, definition in columns.items():
            if name not in existing:
                connection.execute(f"ALTER TABLE incidents ADD COLUMN {name} {definition}")

    def _backfill_incident_events(self, connection) -> None:
        rows = connection.execute(
            """
            SELECT incidents.id, incidents.timestamp, incidents.node_id, incidents.class_label
            FROM incidents
            LEFT JOIN incident_events ON incident_events.incident_id = incidents.id
            WHERE incident_events.id IS NULL
            """
        ).fetchall()
        for row in rows:
            connection.execute(
                """
                INSERT INTO incident_events (
                    incident_id, timestamp, event_type, operator, notes
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    row["id"],
                    row["timestamp"],
                    "created",
                    "device",
                    f"{row['node_id']} reported {row['class_label']}",
                ),
            )

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    def _with_health(
        self,
        device: Dict,
        stale_after_seconds: int,
        offline_after_seconds: int,
    ) -> Dict:
        now = datetime.now(timezone.utc)
        try:
            last_seen = self._parse_timestamp(device["last_seen"])
            age_seconds = max(0, int((now - last_seen).total_seconds()))
        except Exception:
            age_seconds = offline_after_seconds + 1

        if device.get("status") == "revoked":
            health = "revoked"
        elif age_seconds >= offline_after_seconds:
            health = "offline"
        elif age_seconds >= stale_after_seconds:
            health = "stale"
        else:
            health = "online"

        enriched = dict(device)
        enriched["health"] = health
        enriched["seconds_since_seen"] = age_seconds
        enriched["status"] = health
        return enriched

    @staticmethod
    def _device_from_row(row) -> Dict:
        data = dict(row)
        data["labels"] = json.loads(data.pop("labels_json"))
        data["incident_classes"] = json.loads(data.pop("incident_classes_json"))
        data.pop("api_key", None)
        return data

    def register_config(self, config: NodeConfig, status: str = "online") -> DeviceRecord:
        return self.upsert_device(
            DeviceRecord(
                node_id=config.node_id,
                latitude=config.location.latitude,
                longitude=config.location.longitude,
                status=status,
                model_path=config.model_path,
                labels=list(config.labels),
                incident_classes=sorted(config.incident_classes),
                last_seen=self._now(),
            ),
            api_key=config.device_api_key,
        )

    def upsert_device(self, device: DeviceRecord, api_key: str = "") -> DeviceRecord:
        existing_key = self.get_api_key(device.node_id)
        key = api_key or existing_key or ""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO devices (
                    node_id, latitude, longitude, status, model_path, labels_json,
                    incident_classes_json, last_seen, firmware_version, notes, api_key
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(node_id) DO UPDATE SET
                    latitude=excluded.latitude,
                    longitude=excluded.longitude,
                    status=excluded.status,
                    model_path=excluded.model_path,
                    labels_json=excluded.labels_json,
                    incident_classes_json=excluded.incident_classes_json,
                    last_seen=excluded.last_seen,
                    firmware_version=excluded.firmware_version,
                    notes=excluded.notes,
                    api_key=CASE
                        WHEN excluded.api_key != '' THEN excluded.api_key
                        ELSE devices.api_key
                    END
                """,
                (
                    device.node_id,
                    device.latitude,
                    device.longitude,
                    device.status,
                    device.model_path,
                    json.dumps(device.labels),
                    json.dumps(device.incident_classes),
                    device.last_seen,
                    device.firmware_version,
                    device.notes,
                    key,
                ),
            )
        return device

    def heartbeat(
        self,
        node_id: str,
        location: Optional[LocationConfig] = None,
        status: str = "online",
    ) -> DeviceRecord:
        existing = self.get_device(node_id) or {}
        latitude = existing.get("latitude", location.latitude if location else 0.0)
        longitude = existing.get("longitude", location.longitude if location else 0.0)
        device = DeviceRecord(
            node_id=node_id,
            latitude=float(latitude),
            longitude=float(longitude),
            status=status,
            model_path=str(existing.get("model_path", "")),
            labels=list(existing.get("labels", [])),
            incident_classes=list(existing.get("incident_classes", [])),
            last_seen=self._now(),
            firmware_version=str(existing.get("firmware_version", "audio-node-0.1.0")),
            notes=str(existing.get("notes", "")),
        )
        return self.upsert_device(device)

    def get_device(self, node_id: str) -> Optional[Dict]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM devices WHERE node_id = ?",
                (node_id,),
            ).fetchone()
        return self._device_from_row(row) if row else None

    def get_api_key(self, node_id: str) -> str:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT api_key FROM devices WHERE node_id = ?",
                (node_id,),
            ).fetchone()
        return str(row["api_key"]) if row else ""

    def authorize(self, node_id: str, api_key: str) -> bool:
        device = self.get_device(node_id)
        if not device or device.get("status") == "revoked":
            return False
        expected = self.get_api_key(node_id)
        return bool(expected) and api_key == expected

    def rotate_device_key(self, node_id: str, api_key: str = "") -> Optional[Dict]:
        key = api_key or secrets.token_urlsafe(32)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE devices
                SET api_key = ?,
                    status = CASE
                        WHEN status = 'revoked' THEN 'provisioned'
                        ELSE status
                    END
                WHERE node_id = ?
                """,
                (key, node_id),
            )
            if cursor.rowcount == 0:
                return None
        device = self.get_device(node_id)
        if not device:
            return None
        device["device_api_key"] = key
        return device

    def revoke_device(self, node_id: str) -> Optional[Dict]:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE devices SET status = 'revoked', api_key = '' WHERE node_id = ?",
                (node_id,),
            )
            if cursor.rowcount == 0:
                return None
        return self.get_device(node_id)

    def list_devices(self) -> List[Dict]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM devices ORDER BY node_id"
            ).fetchall()
        return [self._device_from_row(row) for row in rows]

    def list_devices_with_health(
        self,
        stale_after_seconds: int,
        offline_after_seconds: int,
    ) -> List[Dict]:
        return [
            self._with_health(device, stale_after_seconds, offline_after_seconds)
            for device in self.list_devices()
        ]

    def get_device_with_health(
        self,
        node_id: str,
        stale_after_seconds: int,
        offline_after_seconds: int,
    ) -> Optional[Dict]:
        device = self.get_device(node_id)
        if not device:
            return None
        return self._with_health(device, stale_after_seconds, offline_after_seconds)

    def health_summary(
        self,
        stale_after_seconds: int,
        offline_after_seconds: int,
    ) -> Dict:
        counts = {"online": 0, "stale": 0, "offline": 0}
        for device in self.list_devices_with_health(
            stale_after_seconds,
            offline_after_seconds,
        ):
            counts[device["health"]] = counts.get(device["health"], 0) + 1
        return counts

    def ensure_devices(self, devices: Iterable[DeviceRecord]) -> None:
        for device in devices:
            self.upsert_device(device)

    def append_incident(self, record: IncidentRecord) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO incidents (
                    timestamp, node_id, class_label, class_index, confidence, verified,
                    incident, latitude, longitude, audio_window_seconds, model_path
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.timestamp,
                    record.node_id,
                    record.class_label,
                    record.class_index,
                    record.confidence,
                    int(record.verified),
                    int(record.incident),
                    record.latitude,
                    record.longitude,
                    record.audio_window_seconds,
                    record.model_path,
                ),
            )
            inserted = cursor.rowcount > 0
            if inserted:
                incident_id = int(cursor.lastrowid)
                self._append_incident_event(
                    connection,
                    incident_id,
                    "created",
                    "device",
                    f"{record.node_id} reported {record.class_label}",
                )
            return inserted

    def _append_incident_event(
        self,
        connection,
        incident_id: int,
        event_type: str,
        operator: str,
        notes: str = "",
    ) -> None:
        connection.execute(
            """
            INSERT INTO incident_events (
                incident_id, timestamp, event_type, operator, notes
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                incident_id,
                self._now(),
                event_type,
                operator,
                notes,
            ),
        )

    @staticmethod
    def _incident_event_from_row(row) -> Dict:
        return dict(row)

    def list_incident_events(self, incident_id: int) -> List[Dict]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM incident_events
                WHERE incident_id = ?
                ORDER BY timestamp ASC, id ASC
                """,
                (incident_id,),
            ).fetchall()
        return [self._incident_event_from_row(row) for row in rows]

    @staticmethod
    def _incident_from_row(row) -> Dict:
        data = dict(row)
        data["verified"] = bool(data["verified"])
        data["incident"] = bool(data["incident"])
        return data

    def list_incidents(self, limit: int = 100, node_id: Optional[str] = None) -> List[Dict]:
        params: List = []
        where = ""
        if node_id:
            where = "WHERE node_id = ?"
            params.append(node_id)
        query = f"SELECT * FROM incidents {where} ORDER BY timestamp ASC, id ASC"
        with self._connect() as connection:
            rows = connection.execute(query, tuple(params)).fetchall()
        records = [self._incident_from_row(row) for row in rows]
        return records[-limit:] if limit else records

    def summary(self, node_id: Optional[str] = None) -> Dict:
        records = self.list_incidents(limit=0, node_id=node_id)
        by_class: Dict[str, int] = {}
        by_device: Dict[str, int] = {}
        by_status: Dict[str, int] = {}
        latest: Optional[Dict] = None

        for record in records:
            by_class[record["class_label"]] = by_class.get(record["class_label"], 0) + 1
            by_device[record["node_id"]] = by_device.get(record["node_id"], 0) + 1
            by_status[record["status"]] = by_status.get(record["status"], 0) + 1
            if latest is None or record["timestamp"] > latest["timestamp"]:
                latest = record

        return {
            "total_incidents": len(records),
            "by_class": by_class,
            "by_device": by_device,
            "by_status": by_status,
            "latest": latest,
        }

    def get_incident(self, incident_id: int) -> Optional[Dict]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM incidents WHERE id = ?",
                (incident_id,),
            ).fetchone()
        return self._incident_from_row(row) if row else None

    def get_incident_by_record(self, record: IncidentRecord) -> Optional[Dict]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM incidents
                WHERE timestamp = ?
                  AND node_id = ?
                  AND class_label = ?
                  AND class_index = ?
                  AND confidence = ?
                """,
                (
                    record.timestamp,
                    record.node_id,
                    record.class_label,
                    record.class_index,
                    record.confidence,
                ),
            ).fetchone()
        return self._incident_from_row(row) if row else None

    def update_incident_status(
        self,
        incident_id: int,
        status: str,
        operator: str,
        notes: str = "",
    ) -> Optional[Dict]:
        if status not in {"open", "acknowledged", "resolved"}:
            raise ValueError("status must be open, acknowledged, or resolved")
        now = self._now()
        if status == "open":
            values = {
                "status": "open",
                "acknowledged_at": "",
                "acknowledged_by": "",
                "resolved_at": "",
                "resolved_by": "",
                "resolution_notes": "",
            }
        elif status == "acknowledged":
            values = {
                "status": "acknowledged",
                "acknowledged_at": now,
                "acknowledged_by": operator,
                "resolved_at": "",
                "resolved_by": "",
                "resolution_notes": "",
            }
        else:
            current = self.get_incident(incident_id) or {}
            values = {
                "status": "resolved",
                "acknowledged_at": current.get("acknowledged_at") or now,
                "acknowledged_by": current.get("acknowledged_by") or operator,
                "resolved_at": now,
                "resolved_by": operator,
                "resolution_notes": notes,
            }
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE incidents
                SET status = ?,
                    acknowledged_at = ?,
                    acknowledged_by = ?,
                    resolved_at = ?,
                    resolved_by = ?,
                    resolution_notes = ?
                WHERE id = ?
                """,
                (
                    values["status"],
                    values["acknowledged_at"],
                    values["acknowledged_by"],
                    values["resolved_at"],
                    values["resolved_by"],
                    values["resolution_notes"],
                    incident_id,
                ),
            )
            if cursor.rowcount == 0:
                return None
            event_type = {
                "open": "reopened",
                "acknowledged": "acknowledged",
                "resolved": "resolved",
            }[status]
            self._append_incident_event(
                connection,
                incident_id,
                event_type,
                operator,
                notes,
            )
        return self.get_incident(incident_id)
