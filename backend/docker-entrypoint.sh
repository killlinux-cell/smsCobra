#!/bin/sh
set -e
echo "[cobra] Migrations..."
python manage.py migrate --noinput
echo "[cobra] Demarrage du serveur sur 0.0.0.0:8000"
exec python manage.py runserver 0.0.0.0:8000
