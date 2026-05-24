#!/bin/sh
# Déploie la traçabilité des acquittements d'alertes dans les rapports (sans rebuild Docker).
set -e
cd "$(dirname "$0")/.."
COMPOSE="docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml"

echo "==> git fetch + reset origin/main"
git fetch origin
git reset --hard origin/main
echo "    Commit : $(git log -1 --oneline)"

echo "==> Vérification fichiers acquittement (disque VPS)"
for f in \
  backend/reports/alert_ack.py \
  backend/reports/activity_feed.py \
  backend/alerts/views.py \
  backend/webadmin/templates/webadmin/rapports.html
do
  if [ ! -f "$f" ]; then
    echo "ERREUR : manquant $f — faites git push depuis le PC puis relancez."
    exit 1
  fi
done
if ! grep -q alert_acknowledged backend/reports/activity_feed.py; then
  echo "ERREUR : activity_feed.py trop ancien (pas alert_acknowledged)."
  exit 1
fi
if ! grep -q 'Notes (acquittements' backend/webadmin/templates/webadmin/rapports.html; then
  echo "ERREUR : rapports.html trop ancien (pas colonne Notes acquittements)."
  exit 1
fi
echo "    OK — sources présentes"

echo "==> Copie reports, alerts, webadmin dans le conteneur api"
$COMPOSE cp backend/reports api:/app/reports
$COMPOSE cp backend/alerts api:/app/alerts
$COMPOSE cp backend/webadmin api:/app/webadmin

echo "==> Vérification dans le conteneur"
$COMPOSE exec api sh -c '
  test -f /app/reports/alert_ack.py || exit 20
  grep -q alert_acknowledged /app/reports/activity_feed.py || exit 21
  grep -q "Notes (acquittements" /app/webadmin/templates/webadmin/rapports.html || exit 22
  echo "    OK — alert_ack + rapports.html dans le conteneur"
' || {
  echo "ERREUR : copie Docker échouée. Essayez : ./scripts/vps-sync-all-features.sh"
  exit 1
}

echo "==> collectstatic + restart api"
$COMPOSE exec api python manage.py collectstatic --noinput
$COMPOSE restart api
sleep 4

echo ""
echo "Terminé."
echo "  1) Rechargez Rapports (Ctrl+F5), acquittez une alerte test."
echo "  2) Vérifiez journal « Alerte acquittée » + colonne Notes."
echo "  3) App mobile admin : recompiler l’APK si vous utilisez l’onglet Rapports."
