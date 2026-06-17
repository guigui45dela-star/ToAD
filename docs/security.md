# Guide de Sécurité

## Avertissement

ToAD manipule des données sensibles (rapports d'audit Active Directory). Une mauvaise configuration peut exposer ces données à des personnes non autorisées.

## Risques identifiés

### Critiques

| Risque | Description | Impact |
|--------|-------------|--------|
| Pas d'authentification | Tout accès réseau peut utiliser l'application | Accès non autorisé aux rapports AD |
| Docker socket exposé | Le conteneur a un accès root au host | Évasion conteneur possible |
| Credentials en clair | Mots de passe dans les fichiers de configuration | Fuite de credentials |
| Ports exposés publiquement | BloodHound, Neo4j accessibles depuis le réseau | Accès direct aux bases de données |

### Élevés

| Risque | Description | Impact |
|--------|-------------|--------|
| Pas de HTTPS | Communications en clair | Interception des données |
| Pas de rate limiting | Pas de protection contre brute-force | Attaques par force brute |
| XSS stocké | Rapports HTML servis sans sanitization | Exécution de code dans le navigateur |

## Checklist de sécurité

### Avant déploiement

- [ ] Changer les mots de passe par défaut dans `.env`
- [ ] Configurer un reverse proxy avec HTTPS
- [ ] Activer l'authentification (Basic Auth minimum)
- [ ] Restreindre les ports BloodHound/Neo4j à localhost
- [ ] Configurer un firewall (iptables/ufw)
- [ ] Vérifier que `.env` est dans `.gitignore`
- [ ] Ne jamais committer `.env` ou `clients/`

### En production

- [ ] Monitoring des accès (logs)
- [ ] Backups réguliers des données
- [ ] Mises à jour de sécurité régulières
- [ ] Rotation des credentials périodique
- [ ] Audit de sécurité annuel

## Configuration sécurisée

### 1. Variables d'environnement

**Ne jamais committer `.env` !**

```bash
# .env (NE JAMAIS COMMITTER)
BLOODHOUND_PASSWORD=mon-mot-de-passe-fort-aleatoire
NEO4J_PASSWORD=un-autre-mot-de-passe-fort
```

```bash
# .env.example (peut être committé)
BLOODHOUND_PASSWORD=change-me
NEO4J_PASSWORD=change-me
```

### 2. Restreindre les ports

**docker-compose.yml :**

```yaml
# BloodHound : accessible uniquement depuis localhost
ports:
  - "127.0.0.1:8080:8080"  # ✅ Bon
  # - "8080:8080"          # ❌ Mauvais (exposé publiquement)

# Neo4j : ne pas exposer du tout
ports:
  - "127.0.0.1:7687:7687"  # ✅ Bon (localhost uniquement)
  # - "7687:7687"          # ❌ Mauvais
```

### 3. Authentification Basic Auth

**Avec nginx :**

```nginx
# /etc/nginx/sites-available/toad
server {
    listen 443 ssl http2;
    server_name toad.example.com;

    ssl_certificate /etc/letsencrypt/live/toad.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/toad.example.com/privkey.pem;

    location / {
        auth_basic "ToAD Access";
        auth_basic_user_file /etc/nginx/.htpasswd;

        proxy_pass http://127.0.0.1:9100;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Créer le fichier htpasswd :**

```bash
# Installer apache2-utils
apt install apache2-utils

# Créer le fichier avec un utilisateur
htpasswd -c /etc/nginx/.htpasswd admin
```

### 4. Firewall

**Avec ufw :**

```bash
# Activer ufw
ufw enable

# Autoriser SSH
ufw allow 22/tcp

# Autoriser HTTPS (ToAD via nginx)
ufw allow 443/tcp

# Autoriser HTTP (redirection vers HTTPS)
ufw allow 80/tcp

# NE PAS ouvrir les ports BloodHound/Neo4j
# ufw allow 8080  # ❌ Ne pas faire
# ufw allow 7687  # ❌ Ne pas faire
# ufw allow 7474  # ❌ Ne pas faire

# Vérifier
ufw status
```

**Avec iptables :**

```bash
# Politique par défaut : tout bloquer
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT ACCEPT

# Autoriser loopback
iptables -A INPUT -i lo -j ACCEPT

# Autoriser connexions établies
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# Autoriser SSH
iptables -A INPUT -p tcp --dport 22 -j ACCEPT

# Autoriser HTTP/HTTPS
iptables -A INPUT -p tcp --dport 80 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -j ACCEPT

# Sauvegarder
iptables-save > /etc/iptables/rules.v4
```

### 5. HTTPS avec Let's Encrypt

```bash
# Installer certbot
apt install certbot python3-certbot-nginx

# Obtenir un certificat
certbot --nginx -d toad.example.com

# Renouvellement automatique (déjà configuré par certbot)
certbot renew --dry-run
```

### 6. Headers de sécurité

**Avec nginx :**

```nginx
server {
    # ...

    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline';" always;
}
```

## Docker Socket

### Risque

Le montage de `/var/run/docker.sock` donne un accès root au host. C'est nécessaire pour que ToAD puisse redémarrer BloodHound, mais c'est un risque de sécurité majeur.

### Mitigations

1. **Ne pas exposer ToAD publiquement** sans authentification forte
2. **Utiliser un utilisateur non-root** dans le conteneur (à implémenter)
3. **Limiter les capacités Docker** (cap-drop all)

### Alternative future

Remplacer l'accès Docker socket par une API dédiée :

```
ToAD → API REST → Docker daemon
       (auth + audit)
```

## Protection des données

### Données sensibles

- Rapports PingCastle (vulnérabilités AD)
- Rapports AD-Miner (chemins d'attaque)
- ZIP SharpHound (données AD brutes)
- Credentials BloodHound/Neo4j

### Bonnes pratiques

1. **Chiffrement au repos** : LUKS pour le disque
2. **Chiffrement en transit** : HTTPS obligatoire
3. **Accès restreint** : VPN + authentification
4. **Backup chiffré** : GPG avant upload cloud
5. **Durée de vie** : Supprimer les données après la mission

### Suppression sécurisée

```bash
# Supprimer un client
curl -X DELETE http://localhost:9100/api/clients/{slug}

# Supprimer complètement les données
shred -u /data/{slug}/sources/sharphound/*.zip
rm -rf /data/{slug}/
```

## Monitoring

### Logs à surveiller

```bash
# Logs application
docker logs audit-ad-web

# Logs BloodHound
docker logs bloodhound-bloodhound-1

# Logs accès nginx
tail -f /var/log/nginx/access.log

# Logs authentification
grep "AUTH" /var/log/nginx/access.log
```

### Alertes

Configurer des alertes pour :
- Échecs d'authentification répétés
- Uploads suspects (taille anormale)
- Erreurs BloodHound/Neo4j
- Espace disque faible

## Mise à jour

### Procédure

```bash
# 1. Backup
./scripts/backup.sh

# 2. Pull nouvelle version
git pull origin main

# 3. Rebuild
docker compose build

# 4. Restart
docker compose up -d

# 5. Vérifier
docker ps
curl http://localhost:9100/api/audits
```

## Incident response

### En cas de compromission

1. **Isoler** : Couper l'accès réseau
   ```bash
   ufw deny 9100
   ufw deny 8080
   ```

2. **Auditer** : Vérifier les logs
   ```bash
   docker logs audit-ad-web --since 24h
   cat /data/events.log
   ```

3. **Rotation** : Changer tous les credentials
   ```bash
   # Modifier .env
   nano .env
   # Restart
   docker compose restart
   ```

4. **Notifier** : Informer les clients affectés

5. **Corriger** : Identifier et corriger la vulnérabilité

## Ressources

- [Docker Security](https://docs.docker.com/engine/security/)
- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CIS Docker Benchmark](https://www.cisecurity.org/benchmark/docker)
- [Nginx Security](https://www.nginx.com/blog/nginx-security-monitoring-logging/)

---

**Dernière mise à jour** : 2024
**Contact** : Voir [CONTRIBUTING.md](../CONTRIBUTING.md)
