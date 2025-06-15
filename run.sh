#!/usr/bin/with-contenv bash

# Запустим твой Python скрипт в фоновом режиме
# Здесь мы используем exec, чтобы скрипт заменил собой процесс run.sh,
# что позволяет Docker правильно обрабатывать сигналы завершения
# Home Assistant Supervisor обычно перенаправляет stdout/stderr в логи
# Python скрипта.

# Убедись, что путь к Python скрипту внутри контейнера правильный
python3 /app/pollers.py