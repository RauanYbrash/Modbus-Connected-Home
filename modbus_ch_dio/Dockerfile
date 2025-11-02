ARG BUILD_FROM
FROM ${BUILD_FROM}

# Устанавливаем Python3 и инструменты для сборки пакетов
RUN apk add --no-cache \
    python3 \
    py3-pip \
    build-base \
    python3-dev \
    libffi-dev \
    openssl-dev

# Создаём рабочую директорию
WORKDIR /app

# Копируем requirements.txt и устанавливаем зависимости
COPY requirements.txt
RUN pip3 install --break-system-packages -r requirements.txt

# Копируем Python-скрипт
COPY pollers.py

# Копируем и делаем исполняемым run.sh
COPY run.sh /run.sh
RUN chmod a+x /run.sh

# Запуск скрипта при старте контейнера
CMD [ "/run.sh" ]

