#!/bin/bash
# ============================================================================
# ToAD - Script de backup
# ============================================================================
# Usage: ./scripts/backup.sh [destination]
# Exemple: ./scripts/backup.sh /backup/toad/
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

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CLIENTS_DIR="$PROJECT_DIR/clients"
BACKUP_DIR="${1:-$PROJECT_DIR/backups}"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="toad_backup_$DATE"
BACKUP_PATH="$BACKUP_DIR/$BACKUP_NAME"

# Bannière
echo -e "${BLUE}"
echo "╔══════════════════════════════════════════╗"
echo "║         ToAD - Backup                    ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"

# ============================================================================
# Vérifications
# ============================================================================

info "Vérification des prérequis..."

# Vérifier que le dossier clients existe
if [ ! -d "$CLIENTS_DIR" ]; then
    error "Dossier clients introuvable : $CLIENTS_DIR"
fi

# Vérifier l'espace disque
CLIENTS_SIZE=$(du -sb "$CLIENTS_DIR" 2>/dev/null | cut -f1)
AVAILABLE_SPACE=$(df -P "$BACKUP_DIR" 2>/dev/null | awk 'NR==2 {print $4*1024}')

if [ -n "$AVAILABLE_SPACE" ] && [ "$CLIENTS_SIZE" -gt "$AVAILABLE_SPACE" ]; then
    error "Espace disque insuffisant. Requis: $(numfmt --to=iec $CLIENTS_SIZE), Disponible: $(numfmt --to=iec $AVAILABLE_SPACE)"
fi

success "Prérequis OK"

# ============================================================================
# Création du backup
# ============================================================================

info "Création du backup..."

# Créer le dossier de backup
mkdir -p "$BACKUP_PATH"

# Backup des données clients
info "Backup des données clients..."
if [ -d "$CLIENTS_DIR" ]; then
    tar -czf "$BACKUP_PATH/clients.tar.gz" -C "$PROJECT_DIR" clients/
    success "Données clients sauvegardées ($(du -sh "$BACKUP_PATH/clients.tar.gz" | cut -f1))"
fi

# Backup de la configuration
info "Backup de la configuration..."

# .env (si existe)
if [ -f "$PROJECT_DIR/.env" ]; then
    cp "$PROJECT_DIR/.env" "$BACKUP_PATH/.env"
    success "Fichier .env sauvegardé"
fi

# docker-compose.yml
if [ -f "$PROJECT_DIR/docker-compose.yml" ]; then
    cp "$PROJECT_DIR/docker-compose.yml" "$BACKUP_PATH/docker-compose.yml"
    success "docker-compose.yml sauvegardé"
fi

# Configuration BloodHound
BH_DIR="$HOME/.config/bloodhound"
if [ -d "$BH_DIR" ]; then
    mkdir -p "$BACKUP_PATH/bloodhound-config"
    cp "$BH_DIR/docker-compose.yml" "$BACKUP_PATH/bloodhound-config/" 2>/dev/null || true
    cp "$BH_DIR/.env" "$BACKUP_PATH/bloodhound-config/" 2>/dev/null || true
    cp "$BH_DIR/bloodhound.config.json" "$BACKUP_PATH/bloodhound-config/" 2>/dev/null || true
    success "Configuration BloodHound sauvegardée"
fi

# ============================================================================
# Backup des bases de données
# ============================================================================

info "Backup des bases de données..."

# Backup Neo4j (via docker exec)
if docker ps | grep -q "bloodhound-graph-db"; then
    info "Backup Neo4j..."
    docker exec bloodhound-graph-db neo4j-admin dump --to=/data/neo4j_backup.dump 2>/dev/null || true
    docker cp bloodhound-graph-db:/data/neo4j_backup.dump "$BACKUP_PATH/neo4j_backup.dump" 2>/dev/null || true
    docker exec bloodhound-graph-db rm /data/neo4j_backup.dump 2>/dev/null || true
    if [ -f "$BACKUP_PATH/neo4j_backup.dump" ]; then
        success "Base Neo4j sauvegardée ($(du -sh "$BACKUP_PATH/neo4j_backup.dump" | cut -f1))"
    else
        warn "Impossible de sauvegarder Neo4j (conteneur peut-être arrêté)"
    fi
fi

# Backup PostgreSQL (via docker exec)
if docker ps | grep -q "bloodhound-app-db"; then
    info "Backup PostgreSQL..."
    docker exec bloodhound-app-db pg_dumpall -U bloodhound > "$BACKUP_PATH/postgres_backup.sql" 2>/dev/null || true
    if [ -f "$BACKUP_PATH/postgres_backup.sql" ] && [ -s "$BACKUP_PATH/postgres_backup.sql" ]; then
        success "Base PostgreSQL sauvegardée ($(du -sh "$BACKUP_PATH/postgres_backup.sql" | cut -f1))"
    else
        warn "Impossible de sauvegarder PostgreSQL (conteneur peut-être arrêté)"
        rm -f "$BACKUP_PATH/postgres_backup.sql"
    fi
fi

# ============================================================================
# Métadonnées du backup
# ============================================================================

info "Création des métadonnées..."

cat > "$BACKUP_PATH/backup_info.json" << EOF
{
    "backup_name": "$BACKUP_NAME",
    "backup_date": "$(date -Iseconds)",
    "backup_size": "$(du -sh "$BACKUP_PATH" | cut -f1)",
    "clients_count": $(ls -1d "$CLIENTS_DIR"/*/ 2>/dev/null | wc -l),
    "toad_version": "1.0.0",
    "hostname": "$(hostname)",
    "files": [
$(ls -1 "$BACKUP_PATH" | sed 's/.*/        "&"/' | paste -sd, | sed 's/^/        /')
    ]
}
EOF

success "Métadonnées créées"

# ============================================================================
# Compression finale
# ============================================================================

info "Compression finale..."

cd "$BACKUP_DIR"
tar -czf "$BACKUP_NAME.tar.gz" "$BACKUP_NAME"
rm -rf "$BACKUP_NAME"

BACKUP_SIZE=$(du -sh "$BACKUP_DIR/$BACKUP_NAME.tar.gz" | cut -f1)

success "Backup compressé : $BACKUP_NAME.tar.gz ($BACKUP_SIZE)"

# ============================================================================
# Nettoyage des anciens backups
# ============================================================================

info "Nettoyage des anciens backups..."

# Garder les 10 derniers backups
BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/toad_backup_*.tar.gz 2>/dev/null | wc -l)
if [ "$BACKUP_COUNT" -gt 10 ]; then
    ls -1t "$BACKUP_DIR"/toad_backup_*.tar.gz | tail -n +11 | xargs rm -f
    success "Anciens backups supprimés (conservation: 10)"
fi

# ============================================================================
# Résumé
# ============================================================================

echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Backup terminé !${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "Fichier : ${BLUE}$BACKUP_DIR/$BACKUP_NAME.tar.gz${NC}"
echo -e "Taille  : ${BLUE}$BACKUP_SIZE${NC}"
echo -e "Date    : ${BLUE}$(date)${NC}"
echo ""
echo "Contenu :"
echo "  - clients.tar.gz (données clients)"
echo "  - .env (configuration)"
echo "  - docker-compose.yml"
echo "  - bloodhound-config/ (configuration BloodHound)"
echo "  - neo4j_backup.dump (base Neo4j)"
echo "  - postgres_backup.sql (base PostgreSQL)"
echo "  - backup_info.json (métadonnées)"
echo ""
warn "Pensez à copier ce backup sur un support externe !"
echo ""
