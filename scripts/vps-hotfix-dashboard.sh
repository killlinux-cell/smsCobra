#!/bin/sh
# Applique les correctifs tableau de bord / passation jour-nuit SANS rebuild Docker
# (utile quand « docker compose build » bloque sur la compilation de dlib).
set -e
cd "$(dirname "$0")/.."
COMPOSE="docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml"

echo "==> git pull"
git pull

echo "==> Copie des fichiers Python dans le conteneur api (sans rebuild)"
$COMPOSE cp backend/webadmin/views.py api:/app/webadmin/views.py
$COMPOSE cp backend/shifts/models.py api:/app/shifts/models.py
$COMPOSE cp backend/shifts/services.py api:/app/shifts/services.py
$COMPOSE cp backend/config/settings.py api:/app/config/settings.py
$COMPOSE cp backend/reports/. api:/app/reports/
$COMPOSE cp backend/alerts/. api:/app/alerts/
if [ -d backend/webadmin/management ]; then
  $COMPOSE cp backend/webadmin/management api:/app/webadmin/
fi

echo "==> Redémarrage api"
$COMPOSE restart api
sleep 3

echo "==> Test scan alertes + passations"
$COMPOSE exec api python -c "
from datetime import timedelta
from django.utils import timezone
from shifts.services import ensure_assignments_for_dates
from alerts.tasks import detect_missed_shift_task
d = timezone.localdate()
ensure_assignments_for_dates([d, d + timedelta(days=1)])
detect_missed_shift_task()
print('OK — scan terminé sans erreur')
"

echo "==> Terminé. Rechargez https://votre-domaine/dashboard/"
