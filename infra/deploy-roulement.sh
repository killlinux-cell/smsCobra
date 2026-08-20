#!/bin/sh
# Déploiement Roulement (phase 1 + 2) sur VPS (/opt/cobra)
# Usage : cd /opt/cobra && sh infra/deploy-roulement.sh

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export COMPOSE="docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml"

echo "=== Arrêt API pour copie des fichiers ==="
$COMPOSE stop api

echo "=== Copie des fichiers Roulement vers le conteneur api ==="

# Accounts
$COMPOSE cp backend/accounts/models.py api:/app/accounts/models.py
$COMPOSE cp backend/accounts/roulement_username.py api:/app/accounts/roulement_username.py
$COMPOSE cp backend/accounts/roulement_convert.py api:/app/accounts/roulement_convert.py
$COMPOSE cp backend/accounts/roulement_eligibility.py api:/app/accounts/roulement_eligibility.py
$COMPOSE cp backend/accounts/migrations/0009_controller_visit_default_visited_at.py api:/app/accounts/migrations/0009_controller_visit_default_visited_at.py
$COMPOSE cp backend/accounts/migrations/0010_user_is_roulement.py api:/app/accounts/migrations/0010_user_is_roulement.py
$COMPOSE cp backend/accounts/migrations/0011_user_roulement_cycle_anchor.py api:/app/accounts/migrations/0011_user_roulement_cycle_anchor.py
$COMPOSE cp backend/accounts/management/commands/normalize_vigile_usernames.py api:/app/accounts/management/commands/normalize_vigile_usernames.py

# Shifts
$COMPOSE cp backend/shifts/models.py api:/app/shifts/models.py
$COMPOSE cp backend/shifts/roulement_assignment.py api:/app/shifts/roulement_assignment.py
$COMPOSE cp backend/shifts/roulement_cycle.py api:/app/shifts/roulement_cycle.py
$COMPOSE cp backend/shifts/slot_occupancy.py api:/app/shifts/slot_occupancy.py
$COMPOSE cp backend/shifts/titular_replacement.py api:/app/shifts/titular_replacement.py
$COMPOSE cp backend/shifts/dispatch_candidates.py api:/app/shifts/dispatch_candidates.py
$COMPOSE cp backend/shifts/migrations/0010_remove_shiftassignment_uniq_shiftassignment_one_outgoing_per_incoming_and_more.py api:/app/shifts/migrations/0010_remove_shiftassignment_uniq_shiftassignment_one_outgoing_per_incoming_and_more.py
$COMPOSE cp backend/shifts/migrations/0011_remove_fixedpost_uniq_active_fixedpost_per_site_shift_and_more.py api:/app/shifts/migrations/0011_remove_fixedpost_uniq_active_fixedpost_per_site_shift_and_more.py
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

echo "=== Démarrage API (entrypoint = migrate + gunicorn) ==="
$COMPOSE up -d api

echo "=== Attente démarrage… ==="
sleep 8
$COMPOSE ps api
$COMPOSE logs api --tail=40

echo ""
echo "=== Test local port 8000 ==="
curl -s -o /dev/null -w "HTTP %{http_code}\n" http://127.0.0.1:8000/dashboard/login/ || true

echo "=== Fin. Vérifiez :"
echo "  - https://smsapp24.com/dashboard/roulement/"
echo "  - https://smsapp24.com/dashboard/sites/<id>/"
