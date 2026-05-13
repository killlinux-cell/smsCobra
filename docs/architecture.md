# SMS (Sécurité Multi Services) - Architecture MVP+

## Composants
- Backend API: Django + DRF
- Mobile agent: Flutter
- Mobile admin: Flutter
- Alerting: Celery + Redis + FCM
- Donnees: PostgreSQL

## Flux principal
1. Le vigile se connecte et consulte son affectation du jour.
2. Il envoie un pointage debut/fin avec GPS (et photo cote API).
3. Le backend valide la geofence et stocke le pointage.
4. Celery verifie les prises de service en retard.
5. Si retard depasse, creation d'alerte et envoi push admin.
6. L'admin acquitte l'alerte ou depeche un remplaçant.
