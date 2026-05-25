#!/bin/sh
# Synchronise le backend dans le conteneur api + migrations. Vérifie que le code est bien présent.
set -e
cd "$(dirname "$0")/.."
COMPOSE="docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml"

echo "==> Mise à jour Git (forcée sur origin/main)"
git fetch origin
git reset --hard origin/main
echo "    Commit : $(git log -1 --oneline)"

echo "==> Vérification des fichiers sur le VPS (disque)"
MISSING=0
for f in \
  backend/sites/migrations/0007_site_site_manager_phone.py \
  backend/sites/migrations/0008_site_latitude_longitude_optional.py \
  backend/shifts/migrations/0009_shiftassignment_status_extra.py \
  backend/webadmin/forms.py \
  backend/webadmin/templates/webadmin/affectations.html \
  backend/webadmin/templates/webadmin/_site_tolerance_sync_script.html \
  backend/reports/alert_ack.py \
  backend/webadmin/templates/webadmin/rapports.html
do
  if [ ! -f "$f" ]; then
    echo "    MANQUANT : $f"
    MISSING=1
  fi
done
if [ "$MISSING" = 1 ]; then
  echo ""
  echo "ERREUR : ces fichiers ne sont pas sur le VPS."
  echo "Depuis votre PC : git push origin main"
  echo "Puis sur le VPS : git fetch origin && git reset --hard origin/main"
  exit 1
fi
if ! grep -q site_manager_phone backend/webadmin/forms.py; then
  echo "ERREUR : backend/webadmin/forms.py est une ancienne version (pas de site_manager_phone)."
  exit 1
fi
echo "    OK — fichiers présents sur le disque du VPS"

echo "==> Copie du code backend dans le conteneur api (contenu des dossiers, pas d imbrication dir/dir)"
for dir in webadmin sites accounts shifts checkins alerts reports config; do
  if [ -d "backend/$dir" ]; then
    echo "    backend/$dir -> /app/$dir/"
    $COMPOSE cp "backend/$dir/." "api:/app/$dir/"
  fi
done

echo "==> Vérification dans le conteneur"
$COMPOSE exec api sh -c '
  test -f /app/sites/migrations/0007_site_site_manager_phone.py || exit 10
  test -f /app/sites/migrations/0008_site_latitude_longitude_optional.py || exit 11
  grep -q site_manager_phone /app/webadmin/forms.py || exit 12
  test -f /app/shifts/migrations/0009_shiftassignment_status_extra.py || exit 13
  grep -q cobra-extra-panel /app/webadmin/templates/webadmin/affectations.html || exit 14
  echo "    OK — sites, shifts 0009, forms, affectations Extra dans le conteneur"
' || {
  echo "ERREUR : la copie Docker n a pas mis à jour le conteneur. Réessayez ou rebuild l image api."
  exit 1
}

echo "==> Migrations sites (0007 responsable, 0008 GPS optionnel)"
$COMPOSE exec api python manage.py migrate sites --noinput

echo "==> Toutes les migrations"
$COMPOSE exec api python manage.py migrate --noinput

echo "==> Fichiers statiques"
$COMPOSE exec api python manage.py collectstatic --noinput

echo "==> Redémarrage api"
$COMPOSE restart api
sleep 4

echo "==> État migrations sites"
$COMPOSE exec api python manage.py showmigrations sites | tail -6

echo ""
echo "Terminé. Rechargez les pages (Ctrl+F5)."
echo "Sites : responsable, GPS optionnel, tolérance relève."
echo "Rapports : colonne Notes + événements « Alerte acquittée » après acquittement."
