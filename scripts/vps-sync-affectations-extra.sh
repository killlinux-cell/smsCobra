#!/bin/sh
# Synchronise Planifier / Extra (affectations) dans le conteneur api + migration shifts 0009.
set -e
cd "$(dirname "$0")/.."
COMPOSE="docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml"

echo "==> Git (origin/main)"
git fetch origin
git reset --hard origin/main
echo "    Commit : $(git log -1 --oneline)"

echo "==> Fichiers requis sur le disque"
for f in \
  backend/shifts/migrations/0009_shiftassignment_status_extra.py \
  backend/shifts/models.py \
  backend/webadmin/forms.py \
  backend/webadmin/views.py \
  backend/webadmin/templates/webadmin/affectations.html
do
  if [ ! -f "$f" ]; then
    echo "ERREUR : manquant — $f"
    echo "Sur votre PC : git push origin main"
    exit 1
  fi
done
if ! grep -q cobra-extra-panel backend/webadmin/templates/webadmin/affectations.html; then
  echo "ERREUR : affectations.html sans panneau Extra (ancienne version)."
  exit 1
fi
echo "    OK"

echo "==> Copie dans le conteneur (backend/DIR/. pas backend/DIR)"
for dir in webadmin shifts checkins alerts accounts; do
  echo "    backend/$dir -> /app/$dir/"
  $COMPOSE cp "backend/$dir/." "api:/app/$dir/"
done

echo "==> Vérification dans le conteneur"
$COMPOSE exec api sh -c '
  test -f /app/shifts/migrations/0009_shiftassignment_status_extra.py || exit 10
  grep -q cobra-extra-panel /app/webadmin/templates/webadmin/affectations.html || exit 11
  grep -q planning_mode /app/webadmin/forms.py || exit 12
  echo "    OK — migration 0009 + template Extra dans le conteneur"
' || {
  echo "ERREUR : copie Docker échouée. Réessayez ou : $COMPOSE build api && $COMPOSE up -d api"
  exit 1
}

echo "==> Migrations"
$COMPOSE exec api python manage.py migrate shifts --noinput
$COMPOSE exec api python manage.py migrate --noinput

echo "==> État shifts"
$COMPOSE exec api python manage.py showmigrations shifts | tail -8

echo "==> Redémarrage api"
$COMPOSE restart api
sleep 3

echo ""
echo "Terminé. Ouvrez Affectations et faites Ctrl+F5."
echo "Mode Extra : le panneau « Renfort Extra » doit apparaître sous le champ Mode."
