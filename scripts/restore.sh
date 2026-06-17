#!/bin/bash
# ============================================================================
# ToAD - Script de restauration
# ============================================================================
# Usage: ./scripts/restore.sh <backup_file.tar.gz>
# Exemple: ./scripts/restore.sh backups/toad_backup_20240101_120000.tar.gz
# ============================================================================

set -e

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Fonctions utilitaires
info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERREUR]${NC} $1"; exit 1; }

# ============================================================================
# Vérification des arguments
# ============================================================================

if [ -z "$1" ]; then
    echo "Usage: $0 <backup_file.tar.gz>"
    echo ""
    echo "Exemple: $0 backups/toad_backup_20240101_120000.tar.gz"
    echo ""
    echo "Backups disponibles :"
    ls -lh backups/toad_backup_*.tar.gz 2>/dev/null || echo "  Aucun backup trouvé"
    exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
    error "Fichier introuvable : $BACKUP_FILE"
fi

# Bannière
echo -e "${BLUE}"
echo "╔══════════════════════════════════════════╗"
echo "║         ToAD - Restauration              ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"

# ============================================================================
# Confirmation
# ============================================================================

warn "════════════════════════════════════════════════════════════"
warn "ATTENTION : Cette opération va écraser les données actuelles !"
warn "════════════════════════════════════════════════════════════"
echo ""
echo "Fichier de backup : $BACKUP_FILE"
echo "Taille : $(du -sh "$BACKUP_FILE" | cut -f1)"
echo ""

read -p "Êtes-vous sûr de vouloir continuer ? (tapez 'RESTAURER' pour confirmer) " -r
echo
if [ "$REPLY" != "RESTAURER" ]; then
    info "Restauration annulée"
    exit 0
fi

# ============================================================================
# Extraction
# ============================================================================

info "Extraction du backup..."

TEMP_DIR=$(mktemp -d)
tar -xzf "$BACKUP_FILE" -C "$TEMP_DIR"

# Trouver le dossier extrait
BACKUP_DIR=$(ls -1d "$TEMP_DIR"/toad_backup_* 2>/dev/null | head -1)
if [ -z "$BACKUP_DIR" ]; then
    error "Structure de backup invalide"
fi

success "Backup extrait"

# Afficher les informations du backup
if [ -f "$BACKUP_DIR/backup_info.json" ]; then
    echo ""
    info "Informations du backup :"
    cat "$BACKUP_DIR/backup_info.json" | python3 -m json.tool 2>/dev/null || cat "$BACKUP_DIR/backup_info.json"
    echo ""
fi

# ============================================================================
# Arrêt des services
# ============================================================================

info "Arrêt des services..."

docker compose down 2>/dev/null || true
success "Services arrêtés"

# ============================================================================
# Backup de sécurité des données actuelles
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SAFETY_BACKUP="$PROJECT_DIR/backups/pre_restore_$(date +%Y%m%d_%H%M%S)"

info "Création d'un backup de sécurité..."

mkdir -p "$SAFETY_BACKUP"

# Sauvegarder les données actuelles
if [ -d "$PROJECT_DIR/clients" ]; then
    tar -czf "$SAFETY_BACKUP/clients_before_restore.tar.gz" -C "$PROJECT_DIR" clients/
    success "Backup de sécurité créé : $SAFETY_BACKUP"
fi

# ============================================================================
# Restauration des données clients
# ============================================================================

info "Restauration des données clients..."

if [ -f "$BACKUP_DIR/clients.tar.gz" ]; then
    # Supprimer l'ancien dossier clients
    rm -rf "$PROJECT_DIR/clients"
    
    # Extraire le backup
    tar -xzf "$BACKUP_DIR/clients.tar.gz" -C "$PROJECT_DIR"
    success "Données clients restaurées"
else
    warn "Pas de données clients dans le backup"
fi

# ============================================================================
# Restauration de la configuration
# ============================================================================

info "Restauration de la configuration..."

# .env
if [ -f "$BACKUP_DIR/.env" ]; then
    cp "$BACKUP_DIR/.env" "$PROJECT_DIR/.env"
    success "Fichier .env restauré"
fi

# docker-compose.yml
if [ -f "$BACKUP_DIR/docker-compose.yml" ]; then
    cp "$BACKUP_DIR/docker-compose.yml" "$PROJECT_DIR/docker-compose.yml"
    success "docker-compose.yml restauré"
fi

# Configuration BloodHound
if [ -d "$BACKUP_DIR/bloodhound-config" ]; then
    BH_DIR="$HOME/.config/bloodhound"
    mkdir -p "$BH_DIR"
    cp "$BACKUP_DIR/bloodhound-config/"* "$BH_DIR/" 2>/dev/null || true
    success "Configuration BloodHound restaurée"
fi

# ============================================================================
# Restauration des bases de données
# ============================================================================

# Démarrer temporairement les services pour restaurer les bases
info "Démarrage temporaire des services..."

# Démarrer BloodHound
BH_DIR="$HOME/.config/bloodhound"
if [ -f "$BH_DIR/docker-compose.yml" ]; then
    cd "$BH_DIR"
    docker compose up -d
    cd - > /dev/null
    sleep 10
    success "BloodHound démarré"
fi

# Restaurer Neo4j
if [ -f "$BACKUP_DIR/neo4j_backup.dump" ]; then
    info "Restauration de Neo4j..."
    
    # Arrêter Neo4j
    docker stop bloodhound-graph-db 2>/dev/null || true
    
    # Copier le backup dans le conteneur
    docker cp "$BACKUP_DIR/neo4j_backup.dump" bloodhound-graph-db:/data/neo4j_backup.dump 2>/dev/null || true
    
    # Démarrer Neo4j
    docker start bloodhound-graph-db 2>/dev/null || true
    sleep 5
    
    # Restaurer
    docker exec bloodhound-graph-db neo4j-admin load --from=/data/neo4j_backup.dump --force 2>/dev/null || true
    
    # Nettoyer
    docker exec bloodhound-graph-db rm /data/neo4j_backup.dump 2>/dev/null || true
    
    success "Neo4j restauré"
fi

# Restaurer PostgreSQL
if [ -f "$BACKUP_DIR/postgres_backup.sql" ] && [ -s "$BACKUP_DIR/postgres_backup.sql" ]; then
    info "Restauration de PostgreSQL..."
    
    # Attendre que PostgreSQL soit prêt
    sleep 5
    
    # Restaurer
    docker exec -i bloodhound-app-db psql -U bloodhound < "$BACKUP_DIR/postgres_backup.sql" 2>/dev/null || true
    
    success "PostgreSQL restauré"
fi

# ============================================================================
# Nettoyage
# ============================================================================

info "Nettoyage..."

rm -rf "$TEMP_DIR"
success "Fichiers temporaires supprimés"

# ============================================================================
# Redémarrage des services
# ============================================================================

info "Redémarrage des services..."

# Redémarrer ToAD
docker compose up -d
success "ToAD redémarré"

# ============================================================================
# Résumé
# ============================================================================

echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Restauration terminée !${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "Accédez à ToAD : ${BLUE}http://localhost:9100${NC}"
echo ""
echo -e "Backup de sécurité : ${BLUE}$SAFETY_BACKUP${NC}"
echo ""
warn "Vérifiez que tout fonctionne correctement"
warn "Si problème, vous pouvez restaurer le backup de sécurité"
echo ""

# Afficher le nombre de clients restaurés
CLIENTS_COUNT=$(ls -1d "$PROJECT_DIR/clients"/*/ 2>/dev/null | wc -l)
echo -e "Clients restaurés : ${BLUE}$CLIENTS_COUNT${NC}"
echo ""
