#!/bin/sh
set -e
# Si la commande Compose / Docker fournit des arguments (ex. Celery), on les execute tels quels.
if [ "$#" -gt 0 ]; then
  exec "$@"
fi
echo "[cobra] Migrations..."
python manage.py migrate --noinput
echo "[cobra] Fichiers statiques (CSS, images dashboard)..."
python manage.py collectstatic --noinput
echo "[cobra] Demarrage Gunicorn sur 0.0.0.0:8000"
exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-3}" \
  --threads "${GUNICORN_THREADS:-4}" \
  --timeout "${GUNICORN_TIMEOUT:-90}" \
  --access-logfile - \
  --error-logfile -
