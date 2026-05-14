# Guide complet de deploiement - Cobra sur InterServer VPS

Ce document decrit une mise en production propre de `Cobra` sur un VPS InterServer (Ubuntu), avec:
- backend Django
- PostgreSQL
- Redis
- Celery worker + Celery beat
- Nginx reverse proxy
- HTTPS (Let's Encrypt)

## 1) Architecture cible

- `api` (Django) expose en interne sur `127.0.0.1:8000`
- `db` (PostgreSQL) non exposee publiquement
- `redis` (broker/result backend Celery) non expose publiquement
- `celery_worker` et `celery_beat` connectes a la meme image backend
- `nginx` en frontal sur `80/443`
- certificats SSL geres par Certbot

## 2) Pre-requis VPS

Sur InterServer, provisionner un VPS Ubuntu 22.04+ avec au minimum:
- 2 vCPU
- 4 Go RAM (recommande pour reconnaissance faciale)
- 40 Go disque SSD

Ports firewall a ouvrir:
- `22` (SSH)
- `80` (HTTP)
- `443` (HTTPS)

## 3) DNS

Configurer les enregistrements DNS (chez votre registrar):
- `A` -> `api.votre-domaine.com` vers IP publique du VPS
- optionnel `A` -> `admin.votre-domaine.com` vers la meme IP

Attendre la propagation DNS avant SSL.

## 4) Preparation serveur

Se connecter en SSH puis installer les outils:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl ca-certificates gnupg lsb-release nginx certbot python3-certbot-nginx
```

Installer Docker + plugin compose:

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
docker --version
docker compose version
```

## 5) Recuperation du projet

```bash
cd /opt
sudo git clone https://github.com/killlinux-cell/smsCobra.git cobra
sudo chown -R $USER:$USER /opt/cobra
cd /opt/cobra
```

## 6) Variables d'environnement production

Le projet inclut deja:
- `backend/.env.example`
- `backend/.env.docker`
- `backend/.env.docker.example`

Pour la production, creer `backend/.env.production` (ne pas committer ce fichier).

Exemple recommande:

```env
DJANGO_SECRET_KEY=remplacer-par-une-cle-longue-et-secrete
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=api.votre-domaine.com,admin.votre-domaine.com

DB_ENGINE=django.db.backends.postgresql
DB_NAME=cobra
DB_USER=cobra
DB_PASSWORD=mot-de-passe-db-tres-fort
DB_HOST=db
DB_PORT=5432

CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

CORS_ALLOWED_ORIGINS=https://admin.votre-domaine.com,https://api.votre-domaine.com
CSRF_TRUSTED_ORIGINS=https://admin.votre-domaine.com,https://api.votre-domaine.com

BIOMETRIC_ENFORCEMENT_MODE=enforce
FACE_VERIFICATION_TOLERANCE=0.55
FACE_VERIFICATION_MODEL=hog
FACE_VERIFICATION_NUM_JITTERS=1

FCM_CREDENTIALS_PATH=/app/secrets/firebase-service-account.json
FCM_PROJECT_ID=votre-project-id-firebase
```

Important:
- `DJANGO_DEBUG=False` en production.
- ne jamais laisser `DJANGO_ALLOWED_HOSTS=*` en prod.
- garder les secrets hors Git.

## 7) Docker Compose production (avec Celery)

Le `infra/docker-compose.yml` actuel est plutot orienté dev (`runserver`, ports DB/Redis publics).  
En prod, utiliser le fichier **deja present dans le depot** : `infra/docker-compose.prod.yml` (copie ci-dessous identique si tu dois le recreer a la main).  
Exemple de variables Django prod : `backend/.env.production.example` → copier en `backend/.env.production` sur le VPS.

**Ordre des actions sur le VPS (apres points 1–6, clone dans `/opt/cobra`) :**

1. Creer `infra/.env.prod` (mot de passe Postgres uniquement) :  
   `cp infra/.env.prod.example infra/.env.prod` puis editer `POSTGRES_PASSWORD`.
2. Creer `backend/.env.production` :  
   `cp backend/.env.production.example backend/.env.production` puis remplir `DJANGO_SECRET_KEY`, aligner `DB_PASSWORD` avec `POSTGRES_PASSWORD`, adapter les domaines si differents de `api.smsapp24.com` / `admin.smsapp24.com`.
3. (Optionnel push) Deposer `backend/secrets/firebase-service-account.json` sur le serveur si tu utilises FCM.
4. Lancer les conteneurs depuis la racine du clone :

```bash
cd /opt/cobra
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml up -d --build
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml ps
```

5. Si le build echoue (memoire), relancer une fois ; verifier les logs :  
   `docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml logs -f api`

Contenu de reference `infra/docker-compose.prod.yml` :

```yaml
services:
  db:
    image: postgres:16
    restart: unless-stopped
    environment:
      POSTGRES_DB: cobra
      POSTGRES_USER: cobra
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U cobra -d cobra"]
      interval: 5s
      timeout: 5s
      retries: 10
      start_period: 10s

  redis:
    image: redis:7
    restart: unless-stopped

  api:
    build:
      context: ../backend
      dockerfile: Dockerfile
    restart: unless-stopped
    env_file:
      - ../backend/.env.production
    environment:
      DB_HOST: db
      DB_PORT: "5432"
      CELERY_BROKER_URL: redis://redis:6379/0
      CELERY_RESULT_BACKEND: redis://redis:6379/0
    command: sh -c "python manage.py migrate --noinput && python manage.py runserver 0.0.0.0:8000"
    ports:
      - "127.0.0.1:8000:8000"
    volumes:
      - api_media:/app/media
      - ../backend/secrets:/app/secrets:ro
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started

  celery_worker:
    build:
      context: ../backend
      dockerfile: Dockerfile
    restart: unless-stopped
    env_file:
      - ../backend/.env.production
    command: celery -A config worker -l info
    volumes:
      - api_media:/app/media
      - ../backend/secrets:/app/secrets:ro
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started

  celery_beat:
    build:
      context: ../backend
      dockerfile: Dockerfile
    restart: unless-stopped
    env_file:
      - ../backend/.env.production
    command: celery -A config beat -l info
    volumes:
      - api_media:/app/media
      - ../backend/secrets:/app/secrets:ro
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started

volumes:
  postgres_data:
  api_media:
```

Si le depot ne contient pas encore `infra/.env.prod.example`, cree `infra/.env.prod` a la main avec une seule ligne : `POSTGRES_PASSWORD=...` (meme valeur que `DB_PASSWORD` dans `backend/.env.production`).

## 8) Initialisation application

Creer le compte dashboard initial:

```bash
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml exec api python manage.py seed_dashboard_admin --username cobra --password "MotDePasseTresFort"
```

Verifier la sante API:

```bash
curl http://127.0.0.1:8000/api/docs/
```

## 9) Nginx reverse proxy

Creer `/etc/nginx/sites-available/cobra`:

```nginx
server {
    listen 80;
    server_name api.votre-domaine.com admin.votre-domaine.com;

    client_max_body_size 20M;

    location /media/ {
        proxy_pass http://127.0.0.1:8000/media/;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Activer le site:

```bash
sudo ln -s /etc/nginx/sites-available/cobra /etc/nginx/sites-enabled/cobra
sudo nginx -t
sudo systemctl reload nginx
```

## 10) SSL Let's Encrypt

```bash
sudo certbot --nginx -d api.votre-domaine.com -d admin.votre-domaine.com
sudo systemctl status certbot.timer
```

Le projet supporte deja le proxy HTTPS via:
- `SECURE_PROXY_SSL_HEADER`
- cookies securises quand `DEBUG=False`.

## 11) Mises a jour applicatives

Procedure standard:

```bash
cd /opt/cobra
git pull
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml up -d --build
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml exec api python manage.py migrate --noinput
```

## 12) Sauvegardes

Base PostgreSQL:

```bash
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml exec -T db pg_dump -U cobra cobra > /opt/backup/cobra_$(date +%F).sql
```

Media:

```bash
docker run --rm -v cobra_api_media:/data -v /opt/backup:/backup alpine sh -c "tar czf /backup/media_$(date +%F).tar.gz -C /data ."
```

Planifier via cron (quotidien + retention).

## 13) Observabilite et logs

Logs services:

```bash
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml logs -f api
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml logs -f celery_worker
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml logs -f celery_beat
```

Verifier ressources VPS:

```bash
docker stats
```

## 14) Points de securite obligatoires

- changer tous les mots de passe par defaut (`cobra/cobra` interdit en prod)
- `DJANGO_SECRET_KEY` fort et unique
- `DJANGO_DEBUG=False`
- DB/Redis non exposes publiquement
- limiter `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` aux vrais domaines
- sauvegardes automatiques + test de restauration
- mises a jour OS et Docker regulieres

## 15) Check-list go-live

- [ ] DNS pointe vers le VPS
- [ ] certif SSL actif (HTTPS OK)
- [ ] API docs accessibles en HTTPS
- [ ] dashboard login accessible
- [ ] creation admin OK
- [ ] pointage mobile OK
- [ ] reconnaissance faciale OK
- [ ] taches Celery executees (alertes automatiques)
- [ ] sauvegarde quotidienne active

## Notes importantes sur l'etat actuel du projet

- L'entree de conteneur backend utilise `runserver` (fonctionne, mais pour haute charge preferer Gunicorn + Nginx).
- Le compose fourni dans le depot est oriente dev; le fichier `docker-compose.prod.yml` ci-dessus est la base recommandee pour InterServer VPS.
- Si vous souhaitez, je peux vous preparer une version `Gunicorn + WhiteNoise` prete a l'emploi dans le code.
