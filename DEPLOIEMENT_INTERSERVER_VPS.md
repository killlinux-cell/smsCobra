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

**Cas le plus courant : tout sur le domaine racine** (ex. `smsapp24.com` — API + dashboard sur la meme origine) :
- Enregistrement **`A`** pour **`@`** (racine) → IP publique du VPS (ex. `153.75.250.81`).
- **`www`** : soit un **`A`** `www` → meme IP, soit un **`CNAME`** `www` → `smsapp24.com` (comme souvent chez l’hebergeur).

**Cas optionnel avec sous-domaines** (si tu separes plus tard `api.` / `admin.`) :
- `A` `api` → IP du VPS ; `A` `admin` → meme IP.

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

Exemple **tout sur la racine** (`smsapp24.com`, API + dashboard) :

```env
DJANGO_SECRET_KEY=remplacer-par-une-cle-longue-et-secrete
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=smsapp24.com,www.smsapp24.com,127.0.0.1,localhost

DB_ENGINE=django.db.backends.postgresql
DB_NAME=cobra
DB_USER=cobra
DB_PASSWORD=mot-de-passe-db-tres-fort
DB_HOST=db
DB_PORT=5432

CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

CORS_ALLOWED_ORIGINS=https://smsapp24.com,https://www.smsapp24.com
CSRF_TRUSTED_ORIGINS=https://smsapp24.com,https://www.smsapp24.com

BIOMETRIC_ENFORCEMENT_MODE=enforce
FACE_VERIFICATION_TOLERANCE=0.55
FACE_VERIFICATION_MODEL=hog
FACE_VERIFICATION_NUM_JITTERS=1

FCM_CREDENTIALS_PATH=/app/secrets/firebase-service-account.json
FCM_PROJECT_ID=votre-project-id-firebase
```

Les apps mobiles : `API_BASE=https://smsapp24.com` (pas de sous-domaine `api.`).

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
   `cp backend/.env.production.example backend/.env.production` puis remplir `DJANGO_SECRET_KEY`, aligner `DB_PASSWORD` avec `POSTGRES_PASSWORD`. Pour tout a la racine, garder `smsapp24.com` et `www.smsapp24.com` dans `DJANGO_ALLOWED_HOSTS`, `CORS_*` et `CSRF_*`.
3. (Notifications push) Copier le JSON Firebase sur le VPS — voir **section 8** (les fichiers dans `backend/secrets/` ne sont pas dans Git).
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

## 8) Notifications push (FCM) — alertes sur l'app Admin

Les fichiers `backend/secrets/*.json` sont **ignores par Git** : un `git pull` sur le VPS **ne les copie pas**. Il faut les deposer **a la main** et configurer **le serveur** + **l'APK Android**.

Guide complementaire a la racine du depot : `FCM_SETUP.txt`.

### 8.1) Deux fichiers distincts

| Fichier | Role | Ou |
|--------|------|-----|
| Compte de service Firebase (`firebase-service-account.json` ou `cobra-security-...json`) | **Serveur** Django envoie les push | VPS : `/opt/cobra/backend/secrets/` |
| `google-services.json` | **App Android** recoit les push | PC : `mobile_admin/android/app/` (puis rebuild APK) |

Un **seul** JSON compte de service suffit sur le VPS (renomme en `firebase-service-account.json` si besoin). Les deux noms locaux (`firebase-service-account.json` et `cobra-security-fabff-...json`) designent en general le **meme projet** : garde un seul fichier sur le serveur.

Telechargement compte de service : Console Firebase → Parametres du projet → **Comptes de service** → Generer une nouvelle cle privee (JSON).

### 8.2) Copier le secret sur le VPS (depuis ton PC)

Sur le VPS, preparer le dossier :

```bash
ssh root@VOTRE_IP_VPS
mkdir -p /opt/cobra/backend/secrets
chmod 700 /opt/cobra/backend/secrets
```

Depuis **PowerShell sur Windows** (adapter utilisateur SSH et chemin) :

```powershell
scp "d:\cobra\backend\secrets\firebase-service-account.json" root@VOTRE_IP_VPS:/opt/cobra/backend/secrets/firebase-service-account.json
```

Si tu n'as que l'autre nom de fichier local :

```powershell
scp "d:\cobra\backend\secrets\cobra-security-fabff-firebase-adminsdk-fbsvc-a5d3ea80d5.json" root@VOTRE_IP_VPS:/opt/cobra/backend/secrets/firebase-service-account.json
```

Sur le VPS :

```bash
chmod 600 /opt/cobra/backend/secrets/firebase-service-account.json
ls -la /opt/cobra/backend/secrets/
```

Le fichier `infra/docker-compose.prod.yml` monte deja `../backend/secrets` vers `/app/secrets` dans les conteneurs `api`, `celery_worker` et `celery_beat`.

### 8.3) Variables dans `backend/.env.production`

Ouvrir le JSON et noter `"project_id"` (ex. `cobra-security-fabff`).

Dans `/opt/cobra/backend/.env.production` :

```env
FCM_CREDENTIALS_PATH=/app/secrets/firebase-service-account.json
FCM_PROJECT_ID=cobra-security-fabff
```

(`FCM_PROJECT_ID` est optionnel pour l'envoi ; le chemin fichier est obligatoire en prod Docker.)

Redemarrer les services qui envoient ou declenchent des alertes :

```bash
cd /opt/cobra
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml up -d api celery_worker celery_beat
```

Verifier dans les logs API :

```bash
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml logs api 2>&1 | tail -50
```

Message attendu : **Firebase Admin initialise** (envoi des notifications push possible).  
Sinon : chemin incorrect, permissions, ou JSON invalide.

**Tableau de bord web** : menu **Push mobile** → bandeau **vert** = serveur pret a envoyer.

### 8.4) Application mobile Admin (Android)

1. Console [Firebase](https://console.firebase.google.com) → meme projet que le compte de service.
2. Ajouter une application **Android** si besoin.
3. **ID du package** : `com.cobrasecurity.israel` (voir `mobile_admin/android/app/build.gradle.kts`).
4. Telecharger `google-services.json` → placer dans :

   `mobile_admin/android/app/google-services.json`

   (Fichier gitignore : il n'est pas sur le VPS, seulement dans l'APK compile.)

5. Rebuild l'app pointee vers la prod :

```powershell
cd d:\cobra\mobile_admin
flutter build apk --release --dart-define=API_BASE=https://smsapp24.com
```

6. Installer l'APK sur le telephone.

### 8.5) Enregistrement du token sur le telephone

1. Se connecter avec un compte **admin** : `super_admin`, `admin_societe` ou `superviseur` (pas un vigile).
2. **Accepter** les notifications quand l'app le demande.
3. Apres connexion, l'app appelle `POST /api/v1/me/fcm-token` automatiquement.
4. Banniere attendue dans l'app : *Notifications : token enregistre*.

Si le message indique *configurez Firebase (google-services.json)* → l'APK a ete compile **sans** ce fichier.

**Alternative** : tableau de bord web → **Push mobile** → coller le token FCM manuellement.

### 8.6) Qui recoit les push et quand

Les notifications partent vers tous les comptes `super_admin`, `admin_societe`, `superviseur` qui ont un `fcm_token` renseigne en base.

| Source | Exemples |
|--------|----------|
| **Celery** (tache periodique ~5 min) | Retard prise de service, passation en retard, absence, fin non pointee… |
| **API / web** | Prise et fin de service vigile, depêche / remplacement |

**Obligatoire** : conteneurs `celery_worker` et `celery_beat` actifs sur le VPS (deja dans `docker-compose.prod.yml`). Sans eux, pas d'alertes automatiques planifiees.

### 8.7) Verification rapide

- [ ] Fichier present : `/opt/cobra/backend/secrets/firebase-service-account.json`
- [ ] `FCM_CREDENTIALS_PATH=/app/secrets/firebase-service-account.json` dans `.env.production`
- [ ] Logs API : Firebase Admin initialise
- [ ] Web → Push mobile : bandeau vert
- [ ] APK rebuild avec `google-services.json` + `API_BASE=https://smsapp24.com`
- [ ] Connexion admin sur telephone + notifications autorisees
- [ ] Declencher une alerte test (retard, pointage, etc.)

### 8.8) Alternative sans fichier sur disque (VPS)

Si tu ne peux pas utiliser `scp`, tu peux coller le JSON entier dans une variable d'environnement (une ligne, selon ton hebergeur) :

```env
FCM_SERVICE_ACCOUNT_JSON={"type":"service_account",...}
```

Le backend lit `FCM_SERVICE_ACCOUNT_JSON` en priorite si le fichier n'existe pas. Moins pratique a maintenir ; le fichier dans `secrets/` reste recommande.

---

## 9) Initialisation application

Creer le compte dashboard initial:

```bash
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml exec api python manage.py seed_dashboard_admin --username cobra --password "MotDePasseTresFort"
```

Verifier la sante API :

- Si `DJANGO_ALLOWED_HOSTS` **ne contient pas** `127.0.0.1`, un `curl http://127.0.0.1:8000/...` renvoie **400** (Django : hôte interdit). Ce n’est pas une panne de l’API.
- Soit tu ajoutes `127.0.0.1,localhost` aux hotes (voir `backend/.env.production.example`), puis tu redemarres les conteneurs ;
- soit tu testes avec l’en-tete **Host** d’un de tes domaines deja autorises :

```bash
curl -s -o /dev/null -w "%{http_code}\n" -H "Host: smsapp24.com" http://127.0.0.1:8000/api/docs/
```

Tu dois obtenir **200**. (Si tu voyais **404** avec `/api/docs/` : ancienne image ; fais `git pull` puis `docker compose ... up -d --build api`. Le code actuel accepte `/api/docs` et `/api/docs/`.)

Apres modification de `.env.production` : `docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml up -d --force-recreate api`.

**Si tu as encore 400 avec `-H "Host: smsapp24.com"`** : Django ne voit pas ce nom dans `ALLOWED_HOSTS`. Verifie **dans le conteneur** :

```bash
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml exec api python -c "from django.conf import settings; print(settings.ALLOWED_HOSTS)"
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml exec api env | grep DJANGO_ALLOWED
```

- Pas de guillemets autour de la valeur dans `.env` (ex. mauvais : `DJANGO_ALLOWED_HOSTS="smsapp24.com..."` — les guillemets peuvent faire partie du nom et casser la validation).
- Pas d’espace avant/apres les virgules (sinon risque de noms invalides selon l’encodage).
- Apres correction : `docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml up -d --force-recreate api`.

## 10) Nginx reverse proxy

Creer `/etc/nginx/sites-available/cobra`:

```nginx
server {
    listen 80;
    server_name smsapp24.com www.smsapp24.com;

    client_max_body_size 20M;

    location /media/ {
        proxy_pass http://127.0.0.1:8000/media/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
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

Activer le site :

```bash
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/cobra /etc/nginx/sites-enabled/cobra
sudo nginx -t
sudo systemctl reload nginx
```

**Lecture des tests `curl` :**

- `curl http://127.0.0.1/` **sans** en-tete `Host:` : souvent **404** — normal, aucun bloc `server_name` ne correspond a `127.0.0.1`.
- `curl -sI -H "Host: smsapp24.com" http://127.0.0.1/` : si les en-tetes contiennent `X-Frame-Options`, `Referrer-Policy`, etc., c’est **Django** qui repond → **Nginx proxifie bien**. Avant une mise a jour du code, un **404** sur la seule URL `/` voulait dire qu’il n’y avait pas de page racine ; le projet redirige maintenant `/` vers `/dashboard/login/` (**302**). Pour valider le service, prefere : `/api/docs/` ou `/dashboard/login/`.

## 11) SSL Let's Encrypt

```bash
sudo certbot --nginx -d smsapp24.com -d www.smsapp24.com
sudo systemctl status certbot.timer
```

Le projet supporte deja le proxy HTTPS via:
- `SECURE_PROXY_SSL_HEADER`
- cookies securises quand `DEBUG=False`.

**Dashboard sans CSS / images cassees** : en production (`DEBUG=False`), Django ne sert pas seul les fichiers `{% static %}`. Le code utilise **WhiteNoise** et lance **`collectstatic`** au demarrage du conteneur `api`. Apres mise a jour du depot : `git pull` puis `docker compose ... up -d --build` (rebuild pour `pip install` + collecte des statiques).

**Installation sur le bureau (PWA)** : le dashboard expose un manifeste (`/dashboard/manifest.webmanifest`) et un service worker. Les utilisateurs peuvent installer l’admin web comme application (Chrome/Edge : bouton *Installer* ou icone dans la barre d’adresse). **HTTPS obligatoire** ; en HTTP local l’installation peut etre refusee par le navigateur.

**Photos vigiles (icone cassee sur `/dashboard/vigiles/`)** : les fichiers sont bien enregistres dans le volume Docker `api_media` (`/app/media/profiles/...`), mais sans route `/media/` en prod le navigateur recevait une **404**. Le code sert maintenant `/media/` aussi quand `DEBUG=False` (Nginx doit continuer a proxyfer `location /media/` vers l’API). Apres `git pull` + rebuild `api`, recharger la page ; les vigiles deja crees devraient afficher leur photo.

## 12) Mises a jour applicatives

Procedure standard:

```bash
cd /opt/cobra
git pull
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml up -d --build
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml exec api python manage.py migrate --noinput
```

## 13) Sauvegardes

Base PostgreSQL:

```bash
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml exec -T db pg_dump -U cobra cobra > /opt/backup/cobra_$(date +%F).sql
```

Media:

```bash
docker run --rm -v cobra_api_media:/data -v /opt/backup:/backup alpine sh -c "tar czf /backup/media_$(date +%F).tar.gz -C /data ."
```

Planifier via cron (quotidien + retention).

## 14) Observabilite et logs

Le conteneur `api` demarre avec **Gunicorn** (voir `backend/docker-entrypoint.sh`). Si le site affiche **502 Bad Gateway** ou **Server Error (500)** :

```bash
cd /opt/cobra
# Etat des conteneurs (api doit etre "Up", pas "Restarting" / "Exited")
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml ps

# Dernieres lignes d'erreur Gunicorn / Django
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml logs --tail=80 api

# Redemarrer uniquement l'API
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml up -d --build api

# Tester depuis le VPS (remplacer le Host si besoin)
curl -sI -H "Host: smsapp24.com" http://127.0.0.1:8000/dashboard/login/
```

**Lecture des symptomes :**

| Symptome | Cause frequente | Action |
|----------|-----------------|--------|
| **502** / connexion refusee | Conteneur `api` arrete, Gunicorn plante au boot | `logs api`, puis `up -d --build api` |
| **500** sur `/dashboard/` | Exception Django (souvent scan alertes ou passation jour/nuit) | `logs api`, `git pull` + rebuild (correctifs recents) |
| **400** avec curl sur `127.0.0.1` | `DJANGO_ALLOWED_HOSTS` sans `127.0.0.1` | Normal ; tester avec `-H "Host: smsapp24.com"` |

### Correctif rapide erreur 500 dashboard (sans rebuild)

Si `docker compose build` **bloque** sur `Building wheel for dlib` (30 min à plusieurs heures), **annulez** le build (`Ctrl+C`). L’ancienne image continue de tourner ; vous pouvez corriger le 500 en copiant le code à chaud :

```bash
cd /opt/cobra
git pull
chmod +x scripts/vps-hotfix-dashboard.sh
./scripts/vps-hotfix-dashboard.sh
```

Ou manuellement :

```bash
cd /opt/cobra
git pull
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml cp backend/webadmin/views.py api:/app/webadmin/views.py
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml cp backend/shifts/models.py api:/app/shifts/models.py
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml cp backend/shifts/services.py api:/app/shifts/services.py
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml restart api
```

Test du scan (affiche la traceback si échec) :

```bash
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml exec api python -c "
from datetime import timedelta
from django.utils import timezone
from shifts.services import ensure_assignments_for_dates
from alerts.tasks import detect_missed_shift_task
d = timezone.localdate()
ensure_assignments_for_dates([d, d + timedelta(days=1)])
detect_missed_shift_task()
print('OK')
"
```

### Rebuild complet (apres correctif dlib)

Le fichier `requirements-face.txt` impose **dlib 19.24.6** (roue binaire) pour éviter la compilation C++ sur le VPS. Rebuild uniquement quand le hotfix ne suffit plus :

```bash
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml build --no-cache api
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml up -d api celery_worker celery_beat
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml exec api python manage.py migrate --noinput
```

Apres `git pull`, en temps normal :

```bash
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml up -d --build api celery_worker celery_beat
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml exec api python manage.py migrate --noinput
```

Logs services :

```bash
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml logs -f api
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml logs -f celery_worker
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml logs -f celery_beat
```

Verifier ressources VPS :

```bash
docker stats
```

## 15) Points de securite obligatoires

- changer tous les mots de passe par defaut (`cobra/cobra` interdit en prod)
- `DJANGO_SECRET_KEY` fort et unique
- `DJANGO_DEBUG=False`
- DB/Redis non exposes publiquement
- limiter `ALLOWED_HOSTS`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS` aux vrais domaines
- sauvegardes automatiques + test de restauration
- mises a jour OS et Docker regulieres
- ne jamais committer `backend/secrets/*.json` ni `google-services.json` (FCM)

## 16) Check-list go-live

- [ ] DNS pointe vers le VPS
- [ ] certif SSL actif (HTTPS OK)
- [ ] API docs : `https://smsapp24.com/api/docs/` (ou `https://www.smsapp24.com/...`)
- [ ] Dashboard : `https://smsapp24.com/dashboard/login/`
- [ ] creation admin OK
- [ ] pointage mobile OK
- [ ] reconnaissance faciale OK
- [ ] taches Celery executees (alertes automatiques)
- [ ] **FCM** : `backend/secrets/firebase-service-account.json` sur le VPS + `FCM_CREDENTIALS_PATH` (section 8)
- [ ] **FCM** : `google-services.json` dans l'APK Admin + token enregistre apres connexion
- [ ] sauvegarde quotidienne active

## Notes importantes sur l'etat actuel du projet

- L'entree du conteneur `api` en production utilise **Gunicorn** + WhiteNoise (statiques).
- Le compose `infra/docker-compose.yml` reste oriente dev local ; `infra/docker-compose.prod.yml` pour le VPS InterServer.
