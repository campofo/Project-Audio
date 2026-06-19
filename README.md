# Forest Defense Audio Field Prototype

This project is the audio-classification edge-node prototype for the Forest Defense Project. It listens to short microphone windows, converts audio into log-mel spectrograms, runs a Keras model, labels the result, and records high-confidence forest-threat detections as local incidents.

The first target is a Raspberry Pi-style monitoring node with a USB microphone and fixed GPS coordinates. Local JSONL incident logs and a FastAPI service provide the integration point for future dashboards, SMS/WhatsApp alerts, GSM, LoRa, smoke sensors, and temperature sensors.

The current system also supports a central multi-device mode: many Raspberry Pi audio nodes can register with one API server, authenticate with device keys, send heartbeats, and upload verified incidents into one SQLite-backed fleet dashboard.

## What It Detects

The placeholder label map is focused on the proposal's audio AI use cases:

- `background`
- `chainsaw`
- `gunshot`
- `fire_crackling`

Important: `config/labels.example.json` and `config/node_config.example.json` contain placeholder labels. Replace them with the exact class order used to train `model1_1.h5` before field use.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

PyAudio may need system audio headers on Raspberry Pi:

```bash
sudo apt-get update
sudo apt-get install -y portaudio19-dev
```

## Run Live Node Mode

```bash
python main.py --config config/node_config.example.json live
```

The CLI prints each prediction with label, confidence, verification status, and incident status. High-confidence configured threat classes are appended to `data/incidents.jsonl`.

## Classify A WAV File

```bash
python main.py --config config/node_config.example.json classify-file sample.wav
```

## Run The Local API

```bash
uvicorn forest_defense.api:app --factory --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000/` for the local dashboard.

Endpoints:

- `GET /health`
- `GET /status`
- `GET /incidents`
- `GET /incidents/summary`
- `POST /classify-file` with a WAV upload field named `file`

## Demo And Diagnostics

Seed sample incidents for a pitch/demo dashboard:

```bash
python main.py --config config/node_config.example.json seed-demo
```

The demo command now seeds multiple devices and incidents so the dashboard shows a small fleet.

Check whether the node config, model file, and runtime dependencies are ready:

```bash
python main.py --config config/node_config.example.json diagnose
```

## Multi-Device Operation

Run one central API server:

```bash
python3 -m uvicorn forest_defense.api:app --factory --host 0.0.0.0 --port 8000
```

Provision each Raspberry Pi node from the central system first. This creates a central registry entry, generates or stores the node's device key, and writes a ready-to-copy node config:

```bash
python main.py --config config/node_config.example.json provision-device \
  --node-id fdp-audio-node-010 \
  --latitude 9.52 \
  --longitude -0.71 \
  --output output/nodes/fdp-audio-node-010.json \
  --notes "Northern reserve boundary"
```

For a real deployment with several stationary nodes, use a CSV manifest instead of provisioning one device at a time:

```bash
python main.py --config config/node_config.example.json provision-fleet \
  --manifest config/fleet_manifest.example.csv \
  --output-dir output/nodes \
  --central-api-url http://forest-command.local:8000
```

The manifest columns are `node_id`, `latitude`, `longitude`, optional `device_api_key`, and optional `notes`. Leave `device_api_key` blank to generate a strong per-node key. Generated configs are written under the output directory and should be copied to each Raspberry Pi as `/etc/forest-defense-audio/node_config.json`.

On the Raspberry Pi, install that generated config as `/etc/forest-defense-audio/node_config.json`. Then register/refresh and report status:

```bash
python main.py --config /etc/forest-defense-audio/node_config.json register-device
python main.py --config /etc/forest-defense-audio/node_config.json heartbeat
python main.py --config /etc/forest-defense-audio/node_config.json sync-incidents
python main.py --config /etc/forest-defense-audio/node_config.json sync-status
```

Central fleet endpoints:

- `GET /devices`
- `GET /devices/{node_id}`
- `POST /devices/register` with `api_key` plus `X-Admin-Key` for new devices, or the existing device key for already-provisioned devices
- `POST /devices/{node_id}/heartbeat` with `X-Device-Key`
- `POST /ingest/incident` with `X-Device-Key`
- `GET /incidents?node_id=<node_id>`
- `GET /incidents/{incident_id}` and `GET /incidents/{incident_id}/events`
- `POST /incidents/{incident_id}/acknowledge` with `X-Admin-Key`
- `POST /incidents/{incident_id}/resolve` with `X-Admin-Key`
- `POST /incidents/{incident_id}/reopen` with `X-Admin-Key`

Central state is stored in `fleet_db_path`, which defaults to `data/fleet.db`. JSONL incident logs remain useful on each field node as an offline buffer before `sync-incidents` pushes data to the central API. The node records successful uploads in `sync_state_path`, so repeated sync attempts skip already accepted incidents and retry only pending ones.

Device health is computed from `last_seen` heartbeats. By default, nodes become `stale` after 300 seconds without a heartbeat and `offline` after 900 seconds. Adjust `stale_after_seconds` and `offline_after_seconds` in the central config for the field network.

Incidents are created with `open` status. Operators can acknowledge alerts when a response unit takes ownership, resolve them after field action, or reopen them if follow-up is needed. Each creation and status change is also written to an incident event timeline for audit and handoff between response teams.

The dashboard at `/` is the first multi-device operations console. It shows all registered nodes, live health state, per-device alert counts, recent incidents, and an incident detail panel. Select an alert to view its audit timeline. Enter the central `admin_api_key` in the dashboard only on a trusted local network, then acknowledge, resolve, or reopen the selected alert with operator notes.

## Raspberry Pi Field Checklist

- Confirm USB microphone appears with `arecord -l`.
- Update `config/node_config.example.json` or create a deployment config with the node ID and fixed GPS coordinates.
- Replace the example `device_api_key` with a unique secret per node before field deployment.
- Confirm `model1_1.h5` is present and labels match its class order.
- Run `python main.py --config <config> live` and confirm live predictions print.
- Trigger a known test sound and confirm incidents are written to the configured JSONL path.
- Start the API and confirm another device on the network can reach `http://<pi-ip>:8000/health`.

## Dataset Roadmap

The next model-training cycle should prioritize Ghana and Northern Savannah Zone field conditions. Collect positive samples for chainsaws, gunshots, fire/crackling, vehicles or motorbikes where relevant, and suspicious human/mechanical activity. Collect negative samples for wind, rain, birds, insects, speech, farm ambience, and normal forest soundscapes.

Keep a manifest that records source, date, location, device, sample rate, label, and consent/usage notes for each clip. Use the resulting dataset to retrain and calibrate confidence thresholds before operational deployment.

Use `data/dataset_manifest.example.csv` as the starting manifest and `docs/MODEL_CARD_TEMPLATE.md` to document every trained model before deployment.

## Raspberry Pi Service Deployment

The `deployment/` folder contains systemd service templates for the live audio node and API. Review the paths and user names before installing:

```bash
chmod +x deployment/install_raspberry_pi.sh
./deployment/install_raspberry_pi.sh
```

After editing `/etc/forest-defense-audio/node_config.json`, enable services:

```bash
sudo systemctl enable --now forest-defense-audio.service
sudo systemctl enable --now forest-defense-audio-api.service
sudo systemctl enable --now forest-defense-audio-heartbeat.timer
sudo systemctl enable --now forest-defense-audio-sync.timer
```

For field nodes, the live audio service continuously classifies microphone windows. The heartbeat timer reports node health every minute, and the sync timer retries local incident uploads every five minutes so a node can catch up after a network outage. Run the API service on the central command device; it is optional on remote audio-only nodes unless you want each Pi to expose its own local test API.
