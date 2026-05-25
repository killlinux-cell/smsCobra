# Guide d'utilisation — SMS (Sécurité Multi Services)

**Logiciel de gestion des pointages, présences et supervision des sites de sécurité**

| | |
|---|---|
| **Éditeur / déploiement** | Solution Cobra / SMS — hébergement type `https://smsapp24.com` |
| **Version document** | 1.0 — mai 2026 |
| **Public** | Administrateurs, superviseurs, vigiles, contrôleurs |
| **Documents techniques associés** | `DEPLOIEMENT_INTERSERVER_VPS.md`, `FCM_SETUP.txt` |

---

## Table des matières

1. [Présentation du système](#1-présentation-du-système)
2. [Accès et rôles utilisateurs](#2-accès-et-rôles-utilisateurs)
3. [Applications disponibles](#3-applications-disponibles)
4. [Tableau de bord web (administration)](#4-tableau-de-bord-web-administration)
5. [Application mobile Admin](#5-application-mobile-admin)
6. [Application mobile Agent (vigile)](#6-application-mobile-agent-vigile)
7. [Contrôleurs et passages sur site](#7-contrôleurs-et-passages-sur-site)
8. [Pointages vigiles : règles métier](#8-pointages-vigiles--règles-métier)
9. [Alertes et notifications push](#9-alertes-et-notifications-push)
10. [Rapports, pointages et exports](#10-rapports-pointages-et-exports)
11. [Dépêches et remplacements](#11-dépêches-et-remplacements)
12. [Postes fixes jour / nuit](#12-postes-fixes-jour--nuit)
13. [FAQ et dépannage](#13-faq-et-dépannage)
14. [Glossaire](#14-glossaire)

---

## 1. Présentation du système

SMS (Sécurité Multi Services) est une plateforme qui permet de :

- **Planifier** les affectations des vigiles sur les sites clients ;
- **Contrôler** les prises de service, présences et fins de service via **géolocalisation** et **reconnaissance faciale** ;
- **Superviser** l’activité grâce à des **alertes** (retards, absences, passation, fin non pointée, etc.) ;
- **Enregistrer** les **passages des contrôleurs** sur les sites ;
- **Produire** des **rapports** et exports pour le suivi RH et opérationnel.

Le système repose sur un **serveur central** (API + base de données) et trois interfaces principales :

| Interface | Utilisateurs |
|-----------|----------------|
| **Site web** `/dashboard/` | Admins, superviseurs |
| **SMS Admin** (Android) | Admins, superviseurs |
| **SMS Agent** (Android) | Vigiles |

---

## 2. Accès et rôles utilisateurs

### 2.1 Rôles

| Rôle | Accès web admin | App Admin | App Agent | Description |
|------|-----------------|-----------|-----------|-------------|
| **Super admin** | Oui | Oui | Non | Configuration complète |
| **Admin société** | Oui | Oui | Non | Gestion quotidienne |
| **Superviseur** | Oui | Oui | Non | Suivi, alertes, dépêches |
| **Contrôleur** | Non | Non | Non* | Passage facial sur site (API dédiée) |
| **Vigile** | Non | Non | Oui | Pointages sur le terrain |

\* Le contrôleur utilise l’identification faciale via l’application ou le flux prévu par l’organisation (pas le tableau de bord web).

### 2.2 Connexion web

1. Ouvrir l’URL fournie par votre organisation (ex. `https://smsapp24.com/dashboard/login/`).
2. Saisir **identifiant** et **mot de passe**.
3. Cliquer sur **Connexion**.

En cas d’oubli de mot de passe, contacter l’administrateur système (réinitialisation depuis la gestion des comptes).

### 2.3 Connexion application mobile

- **SMS Admin** : identifiant + mot de passe (compte admin / superviseur).
- **SMS Agent** : identifiant + mot de passe **ou** connexion par **reconnaissance faciale** si la photo d’enrôlement est enregistrée.

Les applications doivent être configurées pour pointer vers le serveur de production (`API_BASE` défini à la compilation, ex. `https://smsapp24.com`).

---

## 3. Applications disponibles

### 3.1 Site web — Espace administration

- URL type : `https://votre-domaine.com/dashboard/`
- Navigateur récent (Chrome, Edge, Firefox).
- **Installation sur le bureau (recommandé)** : depuis la page de connexion ou le menu latéral, utilisez **« Installer sur le bureau »** (Chrome/Edge : icône dans la barre d’adresse ou menu ⋮ → *Installer l’application* ; Safari Mac : *Fichier → Ajouter au Dock*). L’application s’ouvre alors comme un programme indépendant, sans repasser par les favoris du navigateur. Connexion **HTTPS** obligatoire en production.
- Fonctions complètes : sites, vigiles, affectations, alertes, rapports, exports, dépêches.

### 3.2 SMS Admin (Android)

- Installation de l’APK fourni par l’organisation.
- Onglets : **Accueil**, **Alertes**, **Dépêche**, **Gestion**, **Rapports**.
- Notifications push des alertes (si Firebase configuré sur le téléphone et le serveur).

### 3.3 SMS Agent (Android)

- Réservée aux **vigiles**.
- Pointage : début de service, présence, fin de service.
- Nécessite : GPS activé, photo de profil enregistrée, connexion réseau.

---

## 4. Tableau de bord web (administration)

Après connexion, le menu latéral donne accès aux modules suivants.

### 4.1 Tableau de bord

- Vue d’ensemble : affectations du jour, alertes ouvertes, passages contrôleurs récents, carte des sites.
- Indicateurs rapides pour piloter la journée.

### 4.2 Sites

**Objectif** : définir chaque lieu surveillé (coordonnées GPS, horaires, tolérances).

| Information | Usage |
|-------------|--------|
| Nom, adresse | Identification |
| **Numéro du responsable du site** | Contact opérationnel sur place (**obligatoire** à la création) |
| Fuseau horaire | Calcul des créneaux (ex. Africa/Abidjan) |
| Heures prévues début / fin | Référence planning |
| Tolérance retard (minutes) | Retard à la prise de service ; **la même valeur** est appliquée à l’alerte « relève non arrivée » |
| Fenêtres passation matin / soir | Relève nuit→jour, jour→nuit |
| Rayon géofence + marge GPS | Vérification position au pointage (si GPS renseigné) |
| Latitude / longitude *(optionnel)* | Centre de la zone autorisée ; si vide, pas de contrôle géofence |

**Actions** : créer un site, modifier, consulter la fiche, désactiver si besoin.

### 4.3 Vigiles

**Objectif** : gérer le personnel de sécurité.

- Création avec **photo portrait obligatoire** (reconnaissance faciale).
- Coordonnées, domicile, pièce d’identité (scan), date d’intégration.
- Fiche détaillée : historique, affectations liées.

Sans photo valide, les pointages biométriques peuvent être refusés.

### 4.4 Contrôleurs

**Objectif** : personnes habilitées à **passer sur les sites** (contrôle qualité / ronde).

- Création : identifiant, nom, téléphone, **photo portrait**, **sites autorisés** (cases à cocher, sélection multiple sans Ctrl).
- Liste : présence par jour (filtre date), **dernier passage** (site + date/heure), historique via **Fiche**.
- Un contrôleur n’est **présent** un jour donné que s’au moins un passage facial a été enregistré ce jour-là sur un site autorisé.

### 4.5 Affectations

**Objectif** : planifier **qui** travaille **où**, **quand**.

- Date du créneau, heure de début et de fin, site, vigile.
- Statuts : planifié, remplacé, terminé, manqué.
- Modification / suppression selon droits.

Les affectations peuvent être générées automatiquement à partir des **postes fixes** (voir §12).

### 4.6 Titulaires (postes fixes)

**Objectif** : définir les postes **jour (6h–18h)** et **nuit (18h–6h)** par site.

- Titulaire et remplaçant éventuel ;
- Activation du remplaçant sur le poste ;
- Dates de validité du poste.

Règle métier courante : **2 vigiles minimum** sur un site avec 2 postes (jour + nuit).

### 4.7 Alertes

Liste des alertes système :

| Type | Signification |
|------|----------------|
| Retard prise de service | Pas de début pointé après l’heure + tolérance |
| Passation | Relève en retard |
| Présence | Rappel présence (selon configuration) |
| Fin sans pointage | Début enregistré, pas de fin après la fin prévue |
| Absence | Créneau terminé sans aucune prise de service |

**Actions** : consulter le détail, **acquitter** une alerte traitée.

### 4.8 Push mobile

- Vérifier que le **serveur Firebase** est prêt (bandeau vert).
- Enregistrer le **token FCM** de votre téléphone pour recevoir les notifications sur **SMS Admin**.
- L’app enregistre aussi le token automatiquement à la connexion.

Voir `DEPLOIEMENT_INTERSERVER_VPS.md` section 8 pour la configuration technique.

### 4.9 Rapports

Deux volets :

1. **Journal d’activité** — fil chronologique :
   - Nouveau site, nouveau vigile, **nouveau contrôleur** ;
   - **Passage contrôleur** sur un site ;
   - Affectation planifiée, **dépêche / remplacement vigile** ;
   - Poste fixe configuré, **remplaçant activé** sur poste fixe.

2. **Synthèse des pointages** — tableaux par site / vigile / date, avec colonnes **Retard** et **Absent**.

Filtres : site, vigile, mois ou date précise. **Export CSV** disponible.

**Bilan mensuel** (si vigile + mois sélectionnés) : jours pointés, retards, absences, fins manquantes — aide indicative (non juridique).

### 4.10 Pointages

- Vue **mensuelle** par vigile : jours **présents**, **absents** (planifiés sans service valide), **en cours**, non planifiés.
- Compteurs : planifiés / présents / absents.
- Export CSV des pointages bruts.

Un jour est **présent** si début + fin de service complets et journée non marquée **absente** (voir §8).

### 4.11 Dépêche (dispatch)

- Rechercher une affectation du jour ;
- Désigner un **vigile remplaçant** pour une prise de service non honorée ou un changement urgent ;
- Notification push aux admins et trace dans le journal d’activité.

---

## 5. Application mobile Admin

### 5.1 Accueil

- Indicateurs du jour : affectations, terminées, manquées, alertes ouvertes.
- Actualisation par glissement vers le bas.

### 5.2 Alertes

- Liste des alertes récentes ;
- Acquittement possible selon les droits.

### 5.3 Dépêche

- Même logique que le web : choix d’une affectation et envoi d’un remplaçant.

### 5.4 Gestion

- Liste des **sites** et des **vigiles** ;
- Ajout rapide site / vigile (selon version déployée).

### 5.5 Rapports

- **Activité** : flux d’événements (sites, vigiles, contrôleurs, remplacements…).
- **Pointages** : synthèse des rapports de présence.

### 5.6 Notifications

À la première connexion :

1. Autoriser les **notifications** Android ;
2. Vérifier le message « token enregistré » ;
3. Les alertes importantes arrivent en push (retard, passation, pointages, etc.).

---

## 6. Application mobile Agent (vigile)

### 6.1 Prérequis

- Compte vigile actif ;
- **Photo de profil** enregistrée par l’admin ;
- **GPS** et **caméra** autorisés ;
- Connexion Internet.

### 6.2 Écran principal

Affiche les **affectations du jour** et le créneau actif (si dans la fenêtre horaire).

Boutons principaux :

| Action | Description |
|--------|-------------|
| **Prise de service** | Début du créneau — selfie + position |
| **Présence** | Contrôle en cours de service (après le début) |
| **Fin de service** | Clôture du créneau — selfie + position |

### 6.3 Déroulement d’un pointage

1. Choisir l’action (début / présence / fin).
2. L’application vérifie la **position GPS** (géofence du site).
3. **Selfie** : comparaison avec la photo d’enrôlement.
4. Confirmation ou message d’erreur (hors zone, visage non reconnu, hors créneau, etc.).

### 6.4 Connexion par visage

Si activée : identification par selfie sans saisie du mot de passe (photo de référence requise).

### 6.5 Messages d’erreur fréquents (vigile)

| Message | Cause probable |
|---------|----------------|
| Hors créneau | Pointage en dehors des heures de l’affectation |
| Fin trop tôt | Fin avant l’heure prévue du créneau |
| Relève requis | Fin jour impossible avant la prise de service du vigile de nuit |
| Hors zone | Trop loin du site (GPS) |
| Visage non reconnu | Selfie ou photo d’enrôlement à mettre à jour |
| Prise déjà effectuée | Doublon début ou fin |

---

## 7. Contrôleurs et passages sur site

### 7.1 Principe

Le **contrôleur** se présente sur un site où il est **autorisé**. Il effectue un **passage** enregistré par reconnaissance faciale (et éventuellement identification du site).

### 7.2 Côté administration

- Créer le contrôleur et lier les **sites autorisés**.
- Consulter **Présence** par date et **dernier passage** dans la liste.
- Historique complet sur la **Fiche contrôleur** (comme sur votre capture : site, date/heure, score facial).
- **Rapports → Suivi passages contrôleurs** : tableau **présent / absent**, **sites visités** vs **sites non visités** pour la date choisie, plus l’historique filtré par site ou mois.
- **Fiche site** : historique des passages contrôleurs enregistrés sur ce site.
- **App admin → Rapports → onglet Passages** : même suivi pour le superviseur sur mobile.

### 7.3 Présence / absence contrôleur

- **Présent** (jour J) : au moins 1 passage enregistré ce jour.
- **Absent** : aucun passage ce jour (alors qu’il est attendu selon votre procédure interne).

---

## 8. Pointages vigiles : règles métier

### 8.1 Créneaux types

| Poste | Horaire type |
|-------|----------------|
| **Jour** | 06:00 → 18:00 |
| **Nuit** | 18:00 → 06:00 (lendemain) |

Les horaires exacts suivent l’**affectation** et le **site**.

### 8.2 Prise de service (début)

- Autorisée **uniquement** dans la fenêtre du créneau (date + heures de l’affectation).
- Tolérance de **retard** : paramètre du site (`late_tolerance_minutes`, souvent 15 min).
- Après la tolérance : alerte **retard** + possible marquage « retard » dans le rapport.

### 8.3 Présence

- Possible **après** la prise de service et **avant** la fin.
- Permet de prouver une présence en cours de shift.

### 8.4 Fin de service

- **Interdite** avant l’heure de fin prévue du créneau.
- Sur site **jour/nuit** : le vigile de **jour** ne peut terminer qu’après la **prise de service du vigile de nuit** (passation).
- **Présence** en fin de journée complète : début + fin à l’heure → journée **non absente**.

### 8.5 Absence (journée)

Un vigile est marqué **absent** pour la journée si :

- Aucune prise de service après la fin du créneau ; ou
- Prise de service sans fin pointée après la fin du créneau ; ou
- Fin enregistrée **avant** l’heure prévue.

Les absences apparaissent dans **Rapports** et **Pointages** (badge Absent / compteurs).

### 8.6 Géofence

Le pointage est accepté si la position est dans le **rayon du site** + **marge GPS** (imprécision des téléphones). Hors zone : enregistrement possible mais signalé comme hors périmètre selon configuration.

---

## 9. Alertes et notifications push

### 9.1 Génération des alertes

- **Automatique** (tâches planifiées serveur, ~toutes les 5 minutes) : retards, passations, absences, fins non pointées.
- **Immédiate** : prise/fin de service, dépêche remplacement.

### 9.2 Réception sur téléphone (admins)

1. Serveur : fichier Firebase compte de service configuré (`backend/secrets/`).
2. Téléphone : APK **SMS Admin** compilé avec `google-services.json`.
3. Compte **admin / superviseur** connecté, notifications autorisées.

### 9.3 Acquittement

Traiter l’alerte dans **Alertes** (web ou app) pour suivre ce qui a été pris en charge. L’**administrateur qui acquitte** est enregistré automatiquement :

- dans le **journal d’activité** des **Rapports** (événement « Alerte acquittée ») ;
- dans la colonne **Notes** de la **synthèse des pointages** et dans l’**export CSV** (ligne horodatée : qui a acquitté, type d’alerte, détail).

---

## 10. Rapports, pointages et exports

### 10.1 Journal d’activité

Filtre par **site** et par **date** ou **mois**. Idéal pour audit : qui a été créé, qui a pointé, quels remplacements, **changements de titulaire** (promotion / réintégration), **quelles alertes ont été acquittées et par qui**.

### 10.2 Synthèse pointages

Export **CSV** : date, site, vigile, début, fin, retard (oui/non), absent (oui/non), **notes** (acquittements d’alertes, etc.).

### 10.3 Pointages mensuels

Calendrier par vigile : vert = présent, rouge = absent planifié, jaune = en cours (jour actuel).

### 10.4 Usage RH

Les bilans sont **indicatifs**. Toute sanction ou retenue doit respecter le droit du travail et les procédures internes de l’employeur.

---

## 11. Dépêches et remplacements

### 11.1 Dépêche ponctuelle

- Depuis **Dépêche** (web ou app) : choisir l’affectation concernée et le **remplaçant**.
- L’affectation passe en statut **remplacé** ; le titulaire d’origine est conservé en historique sur l’affectation.
- **Si le vigile absent est titulaire du poste fixe** (jour ou nuit) sur ce site : le remplaçant devient automatiquement **titulaire** ; l’absent est **suspendu** jusqu’à réintégration.
- Les affectations planifiées **à partir du jour de la dépêche** suivent le nouveau titulaire.
- **Rapports** : journal « Titulaire promu (dépêche) » + ligne dans les **notes** de pointage des vigiles concernés.
- Entrée dans le **journal d’activité** : « Dépêche / remplacement vigile ».

### 11.2 Réintégration du titulaire (superviseur)

- **Affectations → Titulaires par site** : si un titulaire est **suspendu**, saisir un **motif valable** (min. 10 caractères) puis **Repositionner le titulaire**.
- Le titulaire d’origine reprend le poste ; les affectations planifiées futures sont alignées.
- **Rapports** : journal « Titulaire réintégré » + notes de pointage (motif enregistré).

### 11.3 Remplaçant temporaire (mode classique)

- Sur poste fixe, option **remplaçant actif** sans changer le titulaire (distinct de la promotion par dépêche).
- Le journal peut afficher « Remplaçant activé (poste fixe) ».

---

## 12. Postes fixes jour / nuit

Pour chaque site avec surveillance continue :

1. Créer le **poste jour** (titulaire 6h–18h).
2. Créer le **poste nuit** (titulaire 18h–6h).
3. Le système lie la **passation** (fin jour conditionnée au début nuit).
4. Les affectations quotidiennes peuvent être **générées** automatiquement pour les dates à venir.

---

## 13. FAQ et dépannage

### Le vigile ne peut pas pointer le début

- Vérifier l’**heure** du téléphone (automatique).
- Vérifier qu’il est dans la **fenêtre** du créneau.
- Vérifier **GPS** et **photo de profil**.

### Le vigile ne peut pas pointer la fin

- Est-ce **avant 18h** (ou fin prévue) ? → normal, refusé.
- Site jour/nuit : le **relève de nuit** a-t-il pointé son **début** ?

### Pas de notification sur le téléphone admin

- Voir section 8 de `DEPLOIEMENT_INTERSERVER_VPS.md` (FCM).
- Vérifier **Push mobile** (bandeau vert) et token enregistré.
- **Celery** worker + beat doivent tourner sur le serveur.

### Photo vigile ne s’affiche pas sur le web

- Vérifier que le serveur sert bien `/media/` en production.
- Recharger la page après mise à jour serveur.

### Contrôleur « absent » alors qu’il est passé

- Vérifier la **date** du filtre présence.
- Vérifier que le passage est sur un **site autorisé** pour ce contrôleur.

### Export CSV vide

- Élargir les filtres (mois, site, vigile).
- Vérifier qu’il existe des rapports sur la période.

---

## 14. Glossaire

| Terme | Définition |
|-------|------------|
| **Affectation** | Créneau planifié : vigile + site + date + horaires |
| **Passation** | Relève entre vigile sortant et vigile entrant (ex. jour → nuit) |
| **Géofence** | Zone GPS autorisée autour du site |
| **FCM** | Firebase Cloud Messaging — notifications push |
| **Pointage** | Enregistrement horodaté (début, présence, fin) |
| **Dépêche** | Remplacement urgent d’un vigile sur une affectation |
| **Poste fixe** | Titulaire (et remplaçant) sur un créneau jour ou nuit récurrent |
| **Contrôleur** | Agent de contrôle ; passage facial sur sites autorisés |
| **was_absent** | Indicateur « journée absente » dans le rapport de pointage |
| **Celery** | Service serveur exécutant les tâches automatiques (alertes) |

---

## Contacts et support

Pour l’**hébergement**, les **comptes**, la **réinitialisation des mots de passe** ou l’**installation des APK**, contacter l’administrateur technique de votre organisation.

Pour la **configuration Firebase (push)** ou le **déploiement serveur**, se référer aux documents techniques du dépôt :

- `DEPLOIEMENT_INTERSERVER_VPS.md`
- `FCM_SETUP.txt`

---

*Document généré pour le projet SMS / Cobra — usage interne et remise client. Toute reproduction doit mentionner la version et la date du guide.*
