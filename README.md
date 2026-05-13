# SMS (Sécurité Multi Services)

Solution web (Django) et mobile (Flutter) pour gestion de presence des vigiles, pointage, alertes de retard et reporting admin.

## Demarrage rapide

### Backend
1. Creer l'environnement virtuel et installer:
   - `python -m venv backend/.venv`
   - `backend/.venv/Scripts/python -m pip install -r backend/requirements.txt`
2. Copier `backend/.env.example` vers `.env` (ou variables d'environnement).
3. Lancer migrations:
   - `backend/.venv/Scripts/python backend/manage.py migrate`
4. Lancer API:
   - `backend/.venv/Scripts/python backend/manage.py runserver`

### Services infra (Postgres + Redis seulement)
- `docker compose -f infra/docker-compose.yml up -d db redis`

### Tout lancer avec Docker (API + Postgres + Redis)
Idéal si tu es sous Windows et que tu veux la **reconnaissance faciale** sans compiler dlib sur ta machine.

1. **Docker Desktop** doit être démarré.
2. Le fichier `backend/.env.docker` (déjà dans le dépôt) sert de configuration pour le conteneur API. Pour le développement **sans Docker**, copie plutôt `backend/.env.example` vers `backend/.env` et adapte `DB_HOST=localhost`.
3. **Construire et démarrer** (depuis la racine du dépôt) :
   - `docker compose -f infra/docker-compose.yml up -d --build`
4. Attends la fin du build (plusieurs minutes la première fois), puis ouvre :
   - API : `http://127.0.0.1:8000/api/docs`
   - Dashboard : `http://127.0.0.1:8000/dashboard/login/`
5. **Première connexion au dashboard (Docker)** : la base Postgres est vide au départ, donc l’ancien compte `cobra` / `cobra` n’existe pas encore. Crée-le une fois :
   - Si tu viens de modifier le code (nouvelle commande Django, etc.), **reconstruis l’image API** puis relance le service :  
     `docker compose -f infra/docker-compose.yml up -d --build api`
   - Puis :  
     `docker compose -f infra/docker-compose.yml exec api python manage.py seed_dashboard_admin`
   - Par défaut : utilisateur **`cobra`**, mot de passe **`cobra`**, rôle **super_admin**.  
   - Autre mot de passe :  
     `docker compose -f infra/docker-compose.yml exec api python manage.py seed_dashboard_admin --username cobra --password "TonMotDePasse"`
6. **Flutter (émulateur Android)** : l’API est sur ta machine, donc par exemple  
   `flutter run --dart-define=API_BASE=http://10.0.2.2:8000`
7. **Arrêter** : `docker compose -f infra/docker-compose.yml down`  
   (les données Postgres restent dans le volume `postgres_data` ; les fichiers médias de l’API dans `api_media`.)

Pour voir les logs de l’API :  
`docker compose -f infra/docker-compose.yml logs -f api`

### Flutter
- `cd mobile_agent && flutter pub get && flutter run`
- `cd mobile_admin && flutter pub get && flutter run`

### Tester l’app vigile (`mobile_agent`) sur un **vrai téléphone**
1. PC et téléphone sur le **même Wi‑Fi**.
2. Trouve l’**IPv4** du PC (PowerShell : `ipconfig`, repère « Carte réseau sans fil Wi‑Fi » → Adresse IPv4, ex. `192.168.1.42`).
3. **Docker** : avec `backend/.env.docker` actuel, `ALLOWED_HOSTS` inclut `*` pour le dev (sinon ajoute ton IP à `DJANGO_ALLOWED_HOSTS` et redémarre `api`). Autorise le port **8000** dans le pare-feu Windows si besoin.
4. Lance l’API (Docker ou `runserver`) pour qu’elle écoute sur toutes les interfaces (Docker mappe déjà `8000:8000`).
5. Sur le téléphone, installe l’app puis lance Flutter avec l’URL du PC :
   - `cd mobile_agent && flutter run --dart-define=API_BASE=http://192.168.1.42:8000`
   - Remplace par **ton** IP. Tu peux aussi générer une APK avec la même `--dart-define`.
6. Le vigile de test doit exister **dans la même base que l’API** (souvent Postgres Docker) avec une **photo de profil** — sinon connexion / pointage refusés. Les comptes de l’ancienne SQLite locale ne sont pas automatiquement copiés.
7. L’app **SMS Agent** n’affiche plus de mot de passe : **selfie direct à l’ouverture** pour identifier le vigile (refus si visage inconnu ou non planifié). Le trafic HTTP vers ton PC est autorisé en clair pour le dev (`usesCleartextTraffic` Android).
8. La connexion visage est restreinte par **`site_id`** : renseigne le site au login pour éviter les confusions entre sites.

### Affectations fixes (titulaire / remplaçant)
- Lors de la création d’une affectation Jour/Nuit dans le dashboard, coche **`Enregistrer comme poste fixe quotidien`**.
- Le moteur génère ensuite automatiquement les affectations de chaque jour pour ces postes fixes.
- En cas d’absence ponctuelle, utilise **Dépêcher un remplaçant** (le titulaire reste la référence fixe pour les jours suivants).

### Admin web moderne (Django + Bootstrap)
- Ouvrir `http://127.0.0.1:8000/dashboard/login/` (compte avec rôle administrateur ou superviseur)
- Tableau de bord: `http://127.0.0.1:8000/dashboard/`
- Tout est gérable depuis l'interface (sites, vigiles, affectations, alertes, rapports, pointages) sans passer par `/admin/`
