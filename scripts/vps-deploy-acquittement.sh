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

echo "==> Copie reports, alerts, webadmin (contenu du dossier, sans sous-répertoire reports/reports)"
# Important : « dir » vers « /app/dir » imbrique souvent en « /app/dir/dir/ » ; utiliser dir/.
$COMPOSE cp backend/reports/. api:/app/reports/
$COMPOSE cp backend/alerts/. api:/app/alerts/
$COMPOSE cp backend/webadmin/. api:/app/webadmin/

echo "==> Vérification dans le conteneur"
$COMPOSE exec api sh -c '
  ok=1
  if test -f /app/reports/alert_ack.py; then
    echo "    OK alert_ack.py"
  elif test -f /app/reports/reports/alert_ack.py; then
    echo "    Réparation : fichiers dans /app/reports/reports/ (ancienne copie)"
    cp -a /app/reports/reports/. /app/reports/
    rm -rf /app/reports/reports
  else
    echo "    MANQUANT : /app/reports/alert_ack.py"
    ok=0
  fi
  if grep -q alert_acknowledged /app/reports/activity_feed.py 2>/dev/null; then
    echo "    OK activity_feed (alert_acknowledged)"
  else
    echo "    MANQUANT : alert_acknowledged dans activity_feed.py"
    ok=0
  fi
  if grep -q "Notes (acquittements" /app/webadmin/templates/webadmin/rapports.html 2>/dev/null; then
    echo "    OK rapports.html"
  elif test -f /app/webadmin/webadmin/templates/webadmin/rapports.html; then
    echo "    Réparation : webadmin imbriqué"
    cp -a /app/webadmin/webadmin/. /app/webadmin/
    rm -rf /app/webadmin/webadmin
    grep -q "Notes (acquittements" /app/webadmin/templates/webadmin/rapports.html || ok=0
  else
    echo "    MANQUANT : colonne Notes dans rapports.html"
    ok=0
  fi
  test "$ok" -eq 1 || exit 1
  echo "    OK — acquittement déployé dans le conteneur"
' || {
  echo ""
  echo "ERREUR : diagnostic :"
  echo "  $COMPOSE exec api ls -la /app/reports/"
  echo "  $COMPOSE exec api ls -la /app/reports/reports/ 2>/dev/null || true"
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
