#!/bin/bash
# ============================================================================
# ToAD - Script d'installation automatique
# ============================================================================
# Usage: ./scripts/setup.sh
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

# Bannière
echo -e "${BLUE}"
echo "╔══════════════════════════════════════════╗"
echo "║         ToAD - Installation              ║"
echo "║   Plateforme Audit Active Directory      ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"

# ============================================================================
# Vérification des prérequis
# ============================================================================

info "Vérification des prérequis..."

# Vérifier Docker
if ! command -v docker &> /dev/null; then
    error "Docker n'est pas installé. Voir https://docs.docker.com/get-docker/"
fi
success "Docker installé: $(docker --version)"

# Vérifier Docker Compose
if ! command -v docker compose &> /dev/null; then
    error "Docker Compose n'est pas installé. Voir https://docs.docker.com/compose/install/"
fi
success "Docker Compose installé: $(docker compose version)"

# Vérifier que Docker est actif
if ! docker info &> /dev/null; then
    error "Docker n'est pas actif. Lancez: sudo systemctl start docker"
fi
success "Docker est actif"

# Vérifier les ports
check_port() {
    if ss -tlnp | grep -q ":$1 "; then
        warn "Le port $1 est déjà utilisé"
        return 1
    fi
    return 0
}

PORTS_OK=true
for port in 9100 8080 7687 7474; do
    if ! check_port $port; then
        PORTS_OK=false
    fi
done

if [ "$PORTS_OK" = false ]; then
    warn "Certains ports sont déjà utilisés. Vérifiez la configuration."
    read -p "Continuer quand même ? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

success "Ports disponibles"

# ============================================================================
# Configuration
# ============================================================================

info "Configuration..."

# Vérifier si .env existe déjà
if [ -f .env ]; then
    warn ".env existe déjà"
    read -p "Voulez-vous le réinitialiser ? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
        success "Ancien .env sauvegardé"
    else
        info "Utilisation du .env existant"
        SKIP_ENV=true
    fi
fi

if [ "$SKIP_ENV" != true ]; then
    # Copier .env.example
    cp .env.example .env
    success ".env créé depuis .env.example"

    # Générer des mots de passe aléatoires
    BH_PASS=$(openssl rand -base64 24 | tr -d '/+=' | head -c 24)
    NEO4J_PASS=$(openssl rand -base64 24 | tr -d '/+=' | head -c 24)

    # Remplacer les mots de passe dans .env
    sed -i "s/BLOODHOUND_PASSWORD=.*/BLOODHOUND_PASSWORD=$BH_PASS/" .env
    sed -i "s/NEO4J_PASSWORD=.*/NEO4J_PASSWORD=$NEO4J_PASS/" .env

    success "Mots de passe générés automatiquement"

    echo ""
    warn "════════════════════════════════════════════════════════════"
    warn "IMPORTANT : Vos mots de passe ont été générés automatiquement"
    warn "════════════════════════════════════════════════════════════"
    echo ""
    echo -e "BloodHound : ${BLUE}admin${NC} / ${BLUE}$BH_PASS${NC}"
    echo -e "Neo4j      : ${BLUE}neo4j${NC} / ${BLUE}$NEO4J_PASS${NC}"
    echo ""
    warn "Sauvegardez ces mots de passe dans un gestionnaire de mots de passe !"
    warn "Ils sont stockés dans .env (n'oubliez pas de ne PAS committer ce fichier)"
    echo ""

    read -p "Appuyez sur Entrée pour continuer..."
fi

# ============================================================================
# Création des dossiers
# ============================================================================

info "Création des dossiers..."

mkdir -p clients
mkdir -p docs/screenshots
success "Dossiers créés"

# ============================================================================
# Installation de BloodHound CE
# ============================================================================

info "Vérification de BloodHound CE..."

BH_DIR="$HOME/.config/bloodhound"

if [ ! -d "$BH_DIR" ]; then
    warn "BloodHound CE n'est pas configuré"
    echo ""
    echo "Téléchargez le docker-compose de BloodHound CE depuis :"
    echo "https://github.com/SpecterOps/BloodHound/blob/main/examples/docker-compose/docker-compose.yml"
    echo ""
    echo "Placez-le dans : $BH_DIR/docker-compose.yml"
    echo ""
    read -p "BloodHound CE est-il déjà installé ? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        warn "Installez BloodHound CE puis relancez ce script"
        exit 0
    fi
fi

# Ajouter restart: unless-stopped si pas déjà fait
if ! grep -q "restart: unless-stopped" "$BH_DIR/docker-compose.yml" 2>/dev/null; then
    warn "Ajout de restart: unless-stopped au docker-compose BloodHound..."
    # Script Python pour ajouter restart policy
    python3 << 'PYTHON_SCRIPT'
import yaml
from pathlib import Path

compose_file = Path.home() / ".config/bloodhound/docker-compose.yml"
if compose_file.exists():
    with open(compose_file) as f:
        config = yaml.safe_load(f)
    
    modified = False
    for service_name, service_config in config.get('services', {}).items():
        if 'restart' not in service_config:
            service_config['restart'] = 'unless-stopped'
            modified = True
    
    if modified:
        with open(compose_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        print("Restart policy ajouté")
PYTHON_SCRIPT
    success "Restart policy ajouté"
fi

# ============================================================================
# Lancement des services
# ============================================================================

info "Lancement de BloodHound CE..."

if [ -f "$BH_DIR/docker-compose.yml" ]; then
    cd "$BH_DIR"
    docker compose up -d
    cd - > /dev/null
    success "BloodHound CE lancé"
else
    warn "Impossible de lancer BloodHound CE (fichier docker-compose.yml introuvable)"
fi

info "Lancement de ToAD..."

docker compose up -d
success "ToAD lancé"

# ============================================================================
# Vérification
# ============================================================================

info "Vérification des services..."

sleep 5

check_service() {
    local name=$1
    local url=$2
    if curl -s -o /dev/null -w "%{http_code}" "$url" | grep -q "200\|301\|302\|401"; then
        success "$name est accessible"
        return 0
    else
        warn "$name n'est pas encore accessible (peut être en cours de démarrage)"
        return 1
    fi
}

check_service "ToAD" "http://localhost:9100"
check_service "BloodHound" "http://localhost:8080"

# ============================================================================
# Résumé
# ============================================================================

echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Installation terminée !${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "Accédez à ToAD : ${BLUE}http://localhost:9100${NC}"
echo -e "BloodHound     : ${BLUE}http://localhost:8080${NC}"
echo ""
echo -e "Identifiants BloodHound :"
echo -e "  Utilisateur : ${BLUE}admin${NC}"
echo -e "  Mot de passe: ${BLUE}$BH_PASS${NC}"
echo ""
warn "N'oubliez pas de :"
echo "  1. Sauvegarder les mots de passe"
echo "  2. Configurer un reverse proxy avec HTTPS"
echo "  3. Activer l'authentification"
echo "  4. Configurer le firewall"
echo ""
echo -e "Documentation : ${BLUE}docs/security.md${NC}"
echo ""
