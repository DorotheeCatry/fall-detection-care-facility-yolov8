# 🐳 Docker pour le Développement - Sécur'Âge

Configuration Docker simplifiée pour le développement local.

## 🚀 Démarrage ultra-rapide

```bash
# Démarrer l'environnement de développement
./scripts/dev.sh start

# L'application sera disponible sur http://localhost:8000
```

## 📋 Prérequis

- Docker
- Docker Compose
- Git

## 🛠️ Commandes disponibles

```bash
# Démarrer
./scripts/dev.sh start

# Arrêter
./scripts/dev.sh stop

# Voir les logs
./scripts/dev.sh logs

# Ouvrir un shell
./scripts/dev.sh shell

# Redémarrer
./scripts/dev.sh restart

# Reconstruire l'image
./scripts/dev.sh build

# Migrations Django
./scripts/dev.sh migrate

# Créer un superutilisateur
./scripts/dev.sh superuser
```

## ✨ Fonctionnalités

- **Hot-reload** : Le code est monté en volume, les changements sont automatiques
- **Base de données persistante** : SQLite dans un volume Docker
- **Médias persistants** : Les images/vidéos sont sauvegardées
- **Accès webcam** : Configuration pour utiliser la caméra locale
- **Logs en temps réel** : Debugging facile

## 🔧 Structure

- `Dockerfile.dev` : Image Docker pour le développement
- `docker-compose.dev.yml` : Orchestration simplifiée
- `scripts/dev.sh` : Script tout-en-un pour le développement

## 🐛 Debugging

```bash
# Voir les logs en temps réel
./scripts/dev.sh logs

# Entrer dans le conteneur
./scripts/dev.sh shell

# Puis dans le conteneur :
poetry run python manage.py shell
poetry run python manage.py test
```

## 📦 Volumes

- `dev_media` : Stockage des images/vidéos
- `dev_db` : Base de données SQLite
- Code source monté en live pour le hot-reload

C'est tout ! Votre environnement de développement Docker est prêt ! 🎉