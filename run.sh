#!/usr/bin/with-contenv bash
set -e
set -u
set -o pipefail

POLL_YAML="/config/modbus/poller.yaml"

if [[ ! -f "$POLL_YAML" ]]; then
  echo "❌ Error: poller.yaml not found!"
  exit 1
fi

DEVICE=$(grep -E '^device:' "$POLL_YAML" | awk '{print $2}')

if [[ -z "$DEVICE" ]]; then
  echo "❌ Error: device not found in poller.yaml!"
  exit 1
fi

echo "✅ Found device: $DEVICE"
exec python3 /app/pollers.py "$DEVICE"
