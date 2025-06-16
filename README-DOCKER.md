# 🐳 Docker Setup pour Sécur'Âge

Ce guide vous explique comment utiliser Docker avec Sécur'Âge.

## 🚀 Démarrage rapide

### Mode développement
```bash
# Démarrage simple
./scripts/deploy.sh dev

# Ou manuellement
docker-compose --profile dev up --build
```

### Mode production
```bash
# 1. Configurer l'environnement
cp .env.example .env
# Éditer .env avec vos paramètres

# 2. Déployer
./scripts/deploy.sh prod
```

## 📦 Structure Docker

- **Dockerfile** : Multi-stage (dev + prod)
- **docker-compose.yml** : Orchestration avec profils
- **scripts/** : Scripts d'automatisation
- **.github/workflows/** : CI/CD automatique

## 🛠️ Commandes utiles

```bash
# Build personnalisé
./scripts/build.sh v1.0.0 ghcr.io/votre-username

# Logs
docker-compose logs -f

# Shell dans le conteneur
docker-compose exec secur-age-dev bash

# Arrêter
docker-compose down
```

## 🌐 Accès

- **Dev** : http://localhost:8000
- **Prod** : http://localhost (via Nginx)

## 📋 Variables d'environnement

Voir `.env.example` pour la configuration complète.

Les fichiers Docker sont maintenant créés ! 🎉