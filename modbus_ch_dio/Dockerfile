ARG BUILD_FROM
FROM ${BUILD_FROM}

# Устанавливаем Python3, pip И необходимые инструменты для сборки
RUN apk add --no-cache python3 py3-pip build-base python3-dev libffi-dev openssl-dev cython # <-- ДОБАВИТЬ cython СЮДА!

# Копируем файл requirements.txt
COPY requirements.txt /app/requirements.txt

# Устанавливаем Python-зависимости из requirements.txt
# Добавляем --break-system-packages
RUN pip3 install --break-system-packages -r /app/requirements.txt

# Копируем твой Python скрипт
COPY pollers.py /app/pollers.py

# Копируем скрипт запуска
COPY run.sh /usr/bin/run.sh

# Делаем скрипт запуска исполняемым
RUN chmod +x /usr/bin/run.sh

# Запускаем скрипт run.sh при старте контейнера
CMD [ "/usr/bin/run.sh" ]