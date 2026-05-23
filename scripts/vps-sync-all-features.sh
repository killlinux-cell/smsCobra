#!/bin/sh
# Synchronise TOUT le backend web (sites, contrôleurs, formulaires, templates, migrations)
# dans le conteneur api SANS rebuild complet. Puis migrate + collectstatic.
#
# À lancer sur le VPS : cd /opt/cobra && chmod +x scripts/vps-sync-all-features.sh && ./scripts/vps-sync-all-features.sh
set -e
cd "$(dirname "$0")/.."
COMPOSE="docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml"

echo "==> git pull"
git pull

echo "==> Copie du code backend dans le conteneur api"
for dir in webadmin sites accounts shifts checkins alerts reports config; do
  if [ -d "backend/$dir" ]; then
    echo "    backend/$dir"
    $COMPOSE cp "backend/$dir" "api:/app/$dir"
  fi
done

echo "==> Migrations (0007 responsable site, 0008 lat/lng optionnels, etc.)"
$COMPOSE exec api python manage.py migrate --noinput

echo "==> Fichiers statiques (CSS cases à cocher, PWA…)"
$COMPOSE exec api python manage.py collectstatic --noinput

echo "==> Redémarrage api"
$COMPOSE restart api
sleep 4

echo "==> Vérification migrations sites"
$COMPOSE exec api python manage.py showmigrations sites | tail -5

echo ""
echo "Terminé. Vérifiez sur le site web :"
echo "  - Sites : numéro responsable, lat/lng optionnels, tolérance = alerte relève"
echo "  - Contrôleurs : cases à cocher pour les sites"
echo ""
echo "App mobile Admin : recompiler l'APK si vous utilisez l'app (les changements Flutter ne passent pas par Docker)."
