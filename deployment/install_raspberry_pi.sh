#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/forest-defense-audio}"
CONFIG_DIR="${CONFIG_DIR:-/etc/forest-defense-audio}"

sudo apt-get update
sudo apt-get install -y python3-venv portaudio19-dev

sudo mkdir -p "$APP_DIR" "$CONFIG_DIR"
sudo cp -R . "$APP_DIR"
sudo cp config/node_config.example.json "$CONFIG_DIR/node_config.json"
sudo chown -R pi:pi "$APP_DIR" "$CONFIG_DIR"

python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/python" -m pip install --upgrade pip
"$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/requirements.txt"

sudo cp "$APP_DIR/deployment/forest-defense-audio.service" /etc/systemd/system/
sudo cp "$APP_DIR/deployment/forest-defense-audio-api.service" /etc/systemd/system/
sudo cp "$APP_DIR/deployment/forest-defense-audio-heartbeat.service" /etc/systemd/system/
sudo cp "$APP_DIR/deployment/forest-defense-audio-heartbeat.timer" /etc/systemd/system/
sudo cp "$APP_DIR/deployment/forest-defense-audio-sync.service" /etc/systemd/system/
sudo cp "$APP_DIR/deployment/forest-defense-audio-sync.timer" /etc/systemd/system/
sudo systemctl daemon-reload

echo "Edit $CONFIG_DIR/node_config.json, then run:"
echo "  sudo systemctl enable --now forest-defense-audio.service"
echo "  sudo systemctl enable --now forest-defense-audio-api.service"
echo "  sudo systemctl enable --now forest-defense-audio-heartbeat.timer"
echo "  sudo systemctl enable --now forest-defense-audio-sync.timer"
