#!/bin/bash

# Script de développement pour Sécur'Âge
# Usage: ./scripts/dev.sh [start|stop|restart|logs|shell|build]

set -e

COMMAND=${1:-start}

case $COMMAND in
    start)
        echo "🚀 Démarrage de Sécur'Âge en mode développement..."
        docker-compose -f docker-compose.dev.yml up --build -d
        echo "✅ Environnement de développement démarré!"
        echo "🌐 Application disponible sur: http://localhost:8000"
        echo "📊 Pour voir les logs: ./scripts/dev.sh logs"
        ;;
    
    stop)
        echo "🛑 Arrêt de l'environnement de développement..."
        docker-compose -f docker-compose.dev.yml down
        echo "✅ Environnement arrêté!"
        ;;
    
    restart)
        echo "🔄 Redémarrage de l'environnement de développement..."
        docker-compose -f docker-compose.dev.yml restart
        echo "✅ Environnement redémarré!"
        ;;
    
    logs)
        echo "📊 Affichage des logs..."
        docker-compose -f docker-compose.dev.yml logs -f
        ;;
    
    shell)
        echo "🐚 Ouverture d'un shell dans le conteneur..."
        docker-compose -f docker-compose.dev.yml exec secur-age-dev bash
        ;;
    
    build)
        echo "🔨 Reconstruction de l'image..."
        docker-compose -f docker-compose.dev.yml build --no-cache
        echo "✅ Image reconstruite!"
        ;;
    
    migrate)
        echo "🔄 Exécution des migrations..."
        docker-compose -f docker-compose.dev.yml exec secur-age-dev poetry run python manage.py migrate
        echo "✅ Migrations terminées!"
        ;;
    
    superuser)
        echo "👤 Création d'un superutilisateur..."
        docker-compose -f docker-compose.dev.yml exec secur-age-dev poetry run python manage.py createsuperuser
        ;;
    
    *)
        echo "❌ Commande inconnue: $COMMAND"
        echo ""
        echo "Commandes disponibles:"
        echo "  start     - Démarre l'environnement de développement"
        echo "  stop      - Arrête l'environnement"
        echo "  restart   - Redémarre l'environnement"
        echo "  logs      - Affiche les logs en temps réel"
        echo "  shell     - Ouvre un shell dans le conteneur"
        echo "  build     - Reconstruit l'image Docker"
        echo "  migrate   - Exécute les migrations Django"
        echo "  superuser - Crée un superutilisateur"
        exit 1
        ;;
esac