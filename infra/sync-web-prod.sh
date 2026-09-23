#!/bin/sh
# Copie le dashboard + fiche site dans le conteneur EN COURS (pas de recreate).
# Usage : cd /opt/cobra && sh infra/sync-web-prod.sh

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export COMPOSE="docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml"

echo "=== Copie webadmin (conteneur api déjà démarré) ==="
$COMPOSE cp backend/webadmin/views.py api:/app/webadmin/views.py
$COMPOSE cp backend/webadmin/pwa.py api:/app/webadmin/pwa.py
$COMPOSE cp backend/webadmin/site_guard_roles.py api:/app/webadmin/site_guard_roles.py
$COMPOSE cp backend/webadmin/templates/webadmin/dashboard.html api:/app/webadmin/templates/webadmin/dashboard.html
$COMPOSE cp backend/webadmin/templates/webadmin/site_detail.html api:/app/webadmin/templates/webadmin/site_detail.html
$COMPOSE cp backend/webadmin/templates/webadmin/_site_guard_table.html api:/app/webadmin/templates/webadmin/_site_guard_table.html

echo "=== Restart API (sans recreer) ==="
$COMPOSE restart api
sleep 6

echo "=== Verification dans le conteneur ==="
$COMPOSE exec -T api grep -F "cobra-kpi-rlt" /app/webadmin/templates/webadmin/dashboard.html
$COMPOSE exec -T api grep -F "Équipe actuelle" /app/webadmin/templates/webadmin/site_detail.html
$COMPOSE exec -T api grep -F '"roulement"' /app/webadmin/views.py

echo "=== HTTP dashboard (Host smsapp24.com) ==="
curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  -H "Host: smsapp24.com" \
  http://127.0.0.1:8000/dashboard/login/

echo "OK. Ouvrez https://smsapp24.com/dashboard/ en navigation privée (Ctrl+Shift+N) pour éviter le cache PWA."
