# 🚀 Guide de Déploiement Sécurisé - ToAD

**Version :** 1.0.0  
**Dernière mise à jour :** 17 juin 2026

---

## 📋 Table des Matières

1. [Introduction](#introduction)
2. [Architecture Recommandée](#architecture-recommandée)
3. [Prérequis Système](#prérequis-système)
4. [Installation de Base](#installation-de-base)
5. [Configuration du Reverse Proxy](#configuration-du-reverse-proxy)
6. [Configuration HTTPS/TLS](#configuration-httpstls)
7. [Configuration du Firewall](#configuration-du-firewall)
8. [Isolation Réseau](#isolation-réseau)
9. [Monitoring et Logs](#monitoring-et-logs)
10. [Backup et Restauration](#backup-et-restauration)
11. [Maintenance](#maintenance)
12. [Checklist Finale](#checklist-finale)

---

## Introduction

Ce guide vous accompagne dans le déploiement sécurisé de ToAD en production. Il couvre l'architecture recommandée, la configuration du reverse proxy, HTTPS, le firewall, et les bonnes pratiques de maintenance.

**⚠️ Important :** Suivez ce guide dans l'ordre. Ne sautez aucune étape.

---

## Architecture Recommandée

### Architecture Simple (1 serveur)

```
┌─────────────────────────────────────────────────────────┐
│                    Internet                              │
└────────────────────┬────────────────────────────────────┘
                     │ HTTPS (443)
                     ▼
┌─────────────────────────────────────────────────────────┐
│              Reverse Proxy (nginx/Traefik)               │
│         - TLS termination                                │
│         - Rate limiting                                  │
│         - Headers de sécurité                            │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP (9100) - Interne uniquement
                     ▼
┌─────────────────────────────────────────────────────────┐
│                    ToAD (Docker)                         │
│         - toad-web:9100                                  │
│         - toad-bloodhound:8080 (interne)                 │
│         - toad-graph-db:7687 (interne)                   │
│         - toad-app-db:5432 (interne)                     │
└─────────────────────────────────────────────────────────┘
```

### Architecture Avancée (Multi-serveurs)

```
┌─────────────────────────────────────────────────────────┐
│                    Internet                              │
└────────────────────┬────────────────────────────────────┘
                     │ HTTPS (443)
                     ▼
┌─────────────────────────────────────────────────────────┐
│              Load Balancer (HAProxy/Traefik)             │
└────────────────────┬────────────────────────────────────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
┌──────────┐  ┌──────────┐  ┌──────────┐
│  ToAD 1  │  │  ToAD 2  │  │  ToAD 3  │
└────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │             │
     └─────────────┼─────────────┘
                   ▼
          ┌────────────────┐
          │  BloodHound    │
          │  (cluster)     │
          └────────────────┘
```

---

## Prérequis Système

### Serveur Minimum

- **OS :** Ubuntu 22.04 LTS, Debian 12, ou équivalent
- **CPU :** 4 cores minimum
- **RAM :** 8 GB minimum (16 GB recommandé)
- **Disk :** 50 GB SSD minimum
- **Network :** 100 Mbps minimum

### Logiciels Requis

```bash
# Mise à jour du système
sudo apt update && sudo apt upgrade -y

# Installation des dépendances
sudo apt install -y \
    docker.io \
    docker-compose-plugin \
    nginx \
    certbot \
    python3-certbot-nginx \
    ufw \
    fail2ban
```

### Vérification Docker

```bash
# Vérifier Docker
docker --version
docker compose version

# Ajouter l'utilisateur au groupe docker
sudo usermod -aG docker $USER
newgrp docker
```

---

## Installation de Base

### 1. Cloner le Repository

```bash
cd /srv
sudo git clone https://github.com/guigui45dela-star/ToAD.git
cd ToAD
```

### 2. Configurer les Variables d'Environnement

```bash
# Copier le fichier d'exemple
sudo cp .env.example .env

# Éditer avec vos valeurs
sudo nano .env
```

**Variables critiques à configurer :**

```bash
# Ports
TOAD_PORT=9100
BLOODHOUND_PORT=8080

# Mots de passe (GÉNÉREZ DES MOTS DE PASSE SÉCURISÉS)
BLOODHOUND_PASSWORD=$(openssl rand -base64 32)
NEO4J_PASSWORD=$(openssl rand -base64 32)
POSTGRES_PASSWORD=$(openssl rand -base64 32)

# Token API (OBLIGATOIRE)
API_TOKEN=$(openssl rand -hex 32)
```

### 3. Sécuriser le fichier .env

```bash
sudo chmod 600 .env
sudo chown root:root .env
```

### 4. Lancer ToAD

```bash
sudo docker compose up -d
```

### 5. Vérifier le Statut

```bash
sudo docker compose ps
sudo docker compose logs -f
```

---

## Configuration du Reverse Proxy

### Option 1 : Nginx (Recommandé)

#### 1. Installer Nginx

```bash
sudo apt install nginx -y
```

#### 2. Créer la Configuration

```bash
sudo nano /etc/nginx/sites-available/toad
```

**Configuration de base :**

```nginx
# Redirect HTTP to HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name toad.votre-domaine.com;

    # Let's Encrypt validation
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    # Redirect all other HTTP to HTTPS
    location / {
        return 301 https://$server_name$request_uri;
    }
}

# HTTPS Server
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name toad.votre-domaine.com;

    # SSL Configuration
    ssl_certificate /etc/letsencrypt/live/toad.votre-domaine.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/toad.votre-domaine.com/privkey.pem;
    
    # Modern SSL Configuration
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:10m;
    ssl_session_tickets off;

    # Security Headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:;" always;
    add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;

    # Rate Limiting
    limit_req_zone $binary_remote_addr zone=toad:10m rate=10r/s;
    limit_req zone=toad burst=20 nodelay;

    # Logging
    access_log /var/log/nginx/toad.access.log;
    error_log /var/log/nginx/toad.error.log;

    # Proxy to ToAD
    location / {
        proxy_pass http://127.0.0.1:9100;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
        
        # Buffering
        proxy_buffering on;
        proxy_buffer_size 4k;
        proxy_buffers 8 4k;
    }

    # Health check endpoint (no rate limiting)
    location /api/health {
        proxy_pass http://127.0.0.1:9100;
        limit_req zone=toad burst=100 nodelay;
    }
}
```

#### 3. Activer la Configuration

```bash
sudo ln -s /etc/nginx/sites-available/toad /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Option 2 : Traefik (Alternative)

#### 1. Créer docker-compose.traefik.yml

```yaml
version: '3.8'

services:
  traefik:
    image: traefik:v2.10
    command:
      - "--api.insecure=false"
      - "--providers.docker=true"
      - "--providers.docker.exposedbydefault=false"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge=true"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web"
      - "--certificatesresolvers.letsencrypt.acme.email=votre-email@domaine.com"
      - "--certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json"
      - "--entrypoints.web.http.redirections.entryPoint.to=websecure"
      - "--entrypoints.web.http.redirections.entryPoint.scheme=https"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - "/var/run/docker.sock:/var/run/docker.sock:ro"
      - "traefik-letsencrypt:/letsencrypt"
    restart: unless-stopped

volumes:
  traefik-letsencrypt:
```

#### 2. Modifier docker-compose.yml de ToAD

Ajouter les labels Traefik au service `toad-web` :

```yaml
services:
  toad-web:
    # ... configuration existante ...
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.toad.rule=Host(`toad.votre-domaine.com`)"
      - "traefik.http.routers.toad.entrypoints=websecure"
      - "traefik.http.routers.toad.tls.certresolver=letsencrypt"
      - "traefik.http.services.toad.loadbalancer.server.port=9100"
      - "traefik.http.middlewares.toad-headers.headers.framedeny=true"
      - "traefik.http.middlewares.toad-headers.headers.sslredirect=true"
      - "traefik.http.middlewares.toad-headers.headers.stsseconds=63072000"
      - "traefik.http.routers.toad.middlewares=toad-headers"
```

---

## Configuration HTTPS/TLS

### 1. Obtenir un Certificat Let's Encrypt

```bash
# Arrêter nginx temporairement
sudo systemctl stop nginx

# Obtenir le certificat
sudo certbot certonly --standalone -d toad.votre-domaine.com

# Redémarrer nginx
sudo systemctl start nginx
```

### 2. Configuration du Renouvellement Automatique

```bash
# Tester le renouvellement
sudo certbot renew --dry-run

# Vérifier le cron
sudo systemctl status certbot.timer
```

### 3. Vérifier la Configuration SSL

```bash
# Tester avec SSL Labs
curl -I https://toad.votre-domaine.com

# Vérifier les certificats
openssl s_client -connect toad.votre-domaine.com:443 -servername toad.votre-domaine.com
```

---

## Configuration du Firewall

### 1. Configurer UFW

```bash
# Réinitialiser UFW
sudo ufw reset

# Configurer les règles par défaut
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Autoriser SSH
sudo ufw allow 22/tcp

# Autoriser HTTP et HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# NE PAS exposer les ports internes
# sudo ufw allow 9100/tcp  # ❌ NE PAS FAIRE
# sudo ufw allow 8080/tcp  # ❌ NE PAS FAIRE
# sudo ufw allow 7474/tcp  # ❌ NE PAS FAIRE
# sudo ufw allow 7687/tcp  # ❌ NE PAS FAIRE

# Activer UFW
sudo ufw enable

# Vérifier le statut
sudo ufw status verbose
```

### 2. Configurer Fail2Ban

```bash
# Créer la configuration
sudo nano /etc/fail2ban/jail.local
```

**Contenu :**

```ini
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[nginx-http-auth]
enabled = true
port = http,https
filter = nginx-http-auth
logpath = /var/log/nginx/toad.error.log

[nginx-limit-req]
enabled = true
port = http,https
filter = nginx-limit-req
logpath = /var/log/nginx/toad.error.log
```

```bash
# Redémarrer Fail2Ban
sudo systemctl restart fail2ban
sudo systemctl status fail2ban
```

---

## Isolation Réseau

### 1. Créer un Réseau Docker Dédié

```bash
sudo docker network create --driver bridge toad-network
```

### 2. Modifier docker-compose.yml

```yaml
networks:
  toad-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16

services:
  toad-web:
    networks:
      - toad-network
    # ... reste de la configuration ...

  toad-bloodhound:
    networks:
      - toad-network
    # ... reste de la configuration ...
```

### 3. Restreindre l'Accès aux Ports Internes

Les services internes (BloodHound, Neo4j, PostgreSQL) ne doivent être accessibles que depuis le réseau Docker interne.

```yaml
services:
  toad-bloodhound:
    ports:
      - "127.0.0.1:8080:8080"  # Accessible uniquement depuis localhost
```

---

## Monitoring et Logs

### 1. Configurer les Logs Docker

```bash
# Créer le dossier de logs
sudo mkdir -p /var/log/toad

# Configurer la rotation des logs
sudo nano /etc/docker/daemon.json
```

**Contenu :**

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

```bash
# Redémarrer Docker
sudo systemctl restart docker
```

### 2. Monitoring Basique

```bash
# Script de monitoring simple
cat > /usr/local/bin/toad-monitor.sh << 'EOF'
#!/bin/bash

# Vérifier que les conteneurs tournent
docker compose -f /srv/ToAD/docker-compose.yml ps | grep -q "Up" || {
    echo "ALERT: ToAD containers are down!" | mail -s "ToAD Alert" admin@votre-domaine.com
}

# Vérifier l'espace disque
df -h /srv | awk 'NR==2 {print $5}' | sed 's/%//' | while read usage; do
    if [ $usage -gt 80 ]; then
        echo "ALERT: Disk usage is at ${usage}%" | mail -s "ToAD Disk Alert" admin@votre-domaine.com
    fi
done

# Vérifier la mémoire
free | awk 'NR==2 {printf "Memory Usage: %.2f%%\n", $3*100/$2}' | while read mem; do
    echo $mem
done
EOF

sudo chmod +x /usr/local/bin/toad-monitor.sh
```

### 3. Configurer Cron pour le Monitoring

```bash
# Ajouter au crontab
sudo crontab -e
```

**Ajouter :**

```cron
# Monitoring toutes les 5 minutes
*/5 * * * * /usr/local/bin/toad-monitor.sh

# Backup quotidien à 2h du matin
0 2 * * * /srv/ToAD/scripts/backup.sh

# Rotation des logs hebdomadaire
0 0 * * 0 find /var/log/toad -name "*.log" -mtime +7 -delete
```

---

## Backup et Restauration

### 1. Script de Backup

```bash
sudo nano /srv/ToAD/scripts/backup.sh
```

**Contenu :**

```bash
#!/bin/bash

BACKUP_DIR="/backup/toad"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/toad_backup_$DATE.tar.gz"

# Créer le dossier de backup
mkdir -p $BACKUP_DIR

# Backup des données clients
tar -czf $BACKUP_FILE \
    -C /srv/ToAD \
    clients/ \
    .env \
    docker-compose.yml

# Backup des volumes Docker
docker run --rm \
    -v toad_postgres-data:/data:ro \
    -v $BACKUP_DIR:/backup \
    alpine \
    tar -czf /backup/postgres_backup_$DATE.tar.gz -C /data .

docker run --rm \
    -v toad_neo4j-data:/data:ro \
    -v $BACKUP_DIR:/backup \
    alpine \
    tar -czf /backup/neo4j_backup_$DATE.tar.gz -C /data .

# Supprimer les backups de plus de 30 jours
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete

# Log
echo "Backup completed: $BACKUP_FILE" >> /var/log/toad/backup.log
```

```bash
sudo chmod +x /srv/ToAD/scripts/backup.sh
```

### 2. Script de Restauration

```bash
sudo nano /srv/ToAD/scripts/restore.sh
```

**Contenu :**

```bash
#!/bin/bash

if [ -z "$1" ]; then
    echo "Usage: $0 <backup_file.tar.gz>"
    exit 1
fi

BACKUP_FILE=$1

# Arrêter ToAD
docker compose down

# Restaurer les données clients
tar -xzf $BACKUP_FILE -C /srv/ToAD

# Redémarrer ToAD
docker compose up -d

echo "Restore completed from: $BACKUP_FILE"
```

```bash
sudo chmod +x /srv/ToAD/scripts/restore.sh
```

---

## Maintenance

### 1. Mise à Jour de ToAD

```bash
# Aller dans le dossier ToAD
cd /srv/ToAD

# Sauvegarder
./scripts/backup.sh

# Tirer les dernières modifications
sudo git pull origin main

# Reconstruire et redémarrer
sudo docker compose down
sudo docker compose up -d --build

# Vérifier
sudo docker compose ps
sudo docker compose logs -f
```

### 2. Rotation des Logs

```bash
# Script de rotation
cat > /usr/local/bin/toad-log-rotate.sh << 'EOF'
#!/bin/bash

# Compresser les logs de plus de 1 jour
find /var/log/toad -name "*.log" -mtime +1 -exec gzip {} \;

# Supprimer les logs compressés de plus de 30 jours
find /var/log/toad -name "*.gz" -mtime +30 -delete
EOF

sudo chmod +x /usr/local/bin/toad-log-rotate.sh
```

### 3. Nettoyage Docker

```bash
# Nettoyer les images inutilisées
docker image prune -f

# Nettoyer les volumes inutilisés (ATTENTION : perte de données)
# docker volume prune -f

# Nettoyer les réseaux inutilisés
docker network prune -f
```

---

## Checklist Finale

Avant de mettre ToAD en production, vérifiez :

### 🔴 Critique

- [ ] Mots de passe sécurisés configurés
- [ ] Token API généré et configuré
- [ ] Reverse proxy configuré avec HTTPS
- [ ] Firewall configuré (UFW)
- [ ] Fail2Ban configuré
- [ ] Ports internes non exposés
- [ ] Backup configuré et testé

### 🟡 Important

- [ ] Monitoring en place
- [ ] Logs configurés avec rotation
- [ ] Certificats SSL/TLS valides
- [ ] Documentation lue et comprise
- [ ] Tests effectués en environnement de test

### 🟢 Recommandé

- [ ] Alertes email configurées
- [ ] Documentation interne créée
- [ ] Procédure de restauration testée
- [ ] Plan de maintenance défini

---

## Support et Ressources

- [Guide de Configuration Sécurisée](security-configuration.md)
- [Documentation API](api-documentation.md)
- [Politique de Sécurité](../SECURITY.md)
- [GitHub Issues](https://github.com/guigui45dela-star/ToAD/issues)

---

**Dernière mise à jour :** 17 juin 2026  
**Version :** 1.0.0

---

**ToAD** - *Centralisez vos audits Active Directory* 🐸
