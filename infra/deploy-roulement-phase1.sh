#!/bin/sh
# Déploiement phase 1 Roulement sur VPS (/opt/cobra)
# Usage : cd /opt/cobra && sh infra/deploy-roulement-phase1.sh

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export COMPOSE="docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml"

echo "=== Copie des fichiers Roulement vers le conteneur api ==="

# Accounts
$COMPOSE cp backend/accounts/models.py api:/app/accounts/models.py
$COMPOSE cp backend/accounts/roulement_username.py api:/app/accounts/roulement_username.py
$COMPOSE cp backend/accounts/roulement_convert.py api:/app/accounts/roulement_convert.py
$COMPOSE cp backend/accounts/migrations/0010_user_is_roulement.py api:/app/accounts/migrations/0010_user_is_roulement.py
$COMPOSE cp backend/accounts/management/commands/normalize_vigile_usernames.py api:/app/accounts/management/commands/normalize_vigile_usernames.py

# Shifts
$COMPOSE cp backend/shifts/models.py api:/app/shifts/models.py
$COMPOSE cp backend/shifts/roulement_assignment.py api:/app/shifts/roulement_assignment.py
$COMPOSE cp backend/shifts/slot_occupancy.py api:/app/shifts/slot_occupancy.py
$COMPOSE cp backend/shifts/titular_replacement.py api:/app/shifts/titular_replacement.py
$COMPOSE cp backend/shifts/dispatch_candidates.py api:/app/shifts/dispatch_candidates.py
$COMPOSE cp backend/shifts/migrations/0012_shiftassignment_status_roulement.py api:/app/shifts/migrations/0012_shiftassignment_status_roulement.py

# Webadmin
$COMPOSE cp backend/webadmin/forms.py api:/app/webadmin/forms.py
$COMPOSE cp backend/webadmin/views.py api:/app/webadmin/views.py
$COMPOSE cp backend/webadmin/urls.py api:/app/webadmin/urls.py
$COMPOSE cp backend/webadmin/site_guard_roles.py api:/app/webadmin/site_guard_roles.py
$COMPOSE cp backend/webadmin/vigile_placement.py api:/app/webadmin/vigile_placement.py
$COMPOSE cp backend/webadmin/templatetags/cobra_tags.py api:/app/webadmin/templatetags/cobra_tags.py
$COMPOSE cp backend/webadmin/templates/webadmin/roulement.html api:/app/webadmin/templates/webadmin/roulement.html
$COMPOSE cp backend/webadmin/templates/webadmin/base.html api:/app/webadmin/templates/webadmin/base.html
$COMPOSE cp backend/webadmin/templates/webadmin/_mobile_nav.html api:/app/webadmin/templates/webadmin/_mobile_nav.html
$COMPOSE cp backend/webadmin/templates/webadmin/vigile_detail.html api:/app/webadmin/templates/webadmin/vigile_detail.html

echo "=== Migrations (obligatoire : colonne is_roulement) ==="
$COMPOSE exec -T api python manage.py migrate --noinput

echo "=== Redémarrage API + workers ==="
$COMPOSE up -d --force-recreate api celery_worker celery_beat

echo "=== Vérification ==="
sleep 3
$COMPOSE ps api
$COMPOSE logs api --tail=30

echo ""
echo "=== Test local port 8000 ==="
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:8000/dashboard/login/ || true

echo "=== Fin. Rechargez https://smsapp24.com/dashboard/ ==="
