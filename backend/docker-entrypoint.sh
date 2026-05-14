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
echo "[cobra] Demarrage du serveur sur 0.0.0.0:8000"
exec python manage.py runserver 0.0.0.0:8000
