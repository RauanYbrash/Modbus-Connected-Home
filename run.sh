#!/usr/bin/with-contenv bash
#!/bin/bash

# Путь к конфигурации poller.yaml
POLL_YAML="/config/modbus/poller.yaml"

# Проверка на существование файла
if [[ ! -f "$POLL_YAML" ]]; then
  echo "Error: poller.yaml not found!"
  exit 1
fi

# Извлечение пути к устройству из poller.yaml
DEVICE=$(grep -oP '(?<=device: ).*' "$POLL_YAML")

# Если путь к устройству не найден, выводим ошибку
if [[ -z "$DEVICE" ]]; then
  echo "Error: device not found in poller.yaml!"
  exit 1
fi

echo "Found device: $DEVICE"
# Запустим твой Python скрипт в фоновом режиме
# Здесь мы используем exec, чтобы скрипт заменил собой процесс run.sh,
# что позволяет Docker правильно обрабатывать сигналы завершения
# Home Assistant Supervisor обычно перенаправляет stdout/stderr в логи
# Python скрипта.

# Убедись, что путь к Python скрипту внутри контейнера правильный
python3 /app/pollers.py "$DEVICE"
