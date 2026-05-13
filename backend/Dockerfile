# API Django COBRA — Linux (dlib / face-recognition pour le pointage visage)
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on

# Paquets système pour compiler dlib + Pillow + psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    pkg-config \
    libpq-dev \
    libopenblas-dev \
    liblapack-dev \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    libpng-dev \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements-face.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt -r requirements-face.txt

COPY . .

# Évite les erreurs « /bin/sh^M » si le dépôt est cloné sous Windows (CRLF).
RUN sed -i 's/\r$//' docker-entrypoint.sh && chmod +x docker-entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
