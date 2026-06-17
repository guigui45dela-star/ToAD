# Architecture Technique

## Vue d'ensemble

ToAD est une plateforme web qui orchestre plusieurs outils d'audit Active Directory pour fournir une expérience centralisée et automatisée.

## Composants

### 1. Application Web (ToAD)

**Technologie :** FastAPI (Python 3.12)

**Responsabilités :**
- Interface utilisateur (SPA vanilla JS)
- API REST pour toutes les opérations
- Gestion des fichiers (upload, stockage, téléchargement)
- Orchestration des outils externes (BloodHound, AD-Miner)
- Système de jobs en arrière-plan

**Structure :**
```
web/
├── app.py          # Backend FastAPI (720 lignes)
│   ├── Routes API (14 endpoints)
│   ├── Système de jobs (threading)
│   ├── Intégration BloodHound (API REST)
│   ├── Intégration AD-Miner (subprocess)
│   └── Gestion fichiers (filesystem)
└── index.html      # Frontend SPA (1684 lignes)
    ├── HTML structure
    ├── CSS inline (dark theme)
    └── JavaScript vanilla
```

**Endpoints API principaux :**

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/audits` | GET | Liste tous les clients |
| `/api/clients` | POST | Crée un nouveau client |
| `/api/clients/{slug}` | DELETE | Supprime un client |
| `/api/clients/{slug}/pingcastle` | POST | Upload rapport PingCastle |
| `/api/clients/{slug}/sharphound` | POST | Upload ZIP SharpHound → BloodHound |
| `/api/clients/{slug}/ad-miner/generate` | POST | Génère rapport AD-Miner |
| `/api/audits/full` | POST | Audit complet (PingCastle + SharpHound + AD-Miner) |
| `/api/bloodhound/reset` | POST | Reset BloodHound (docker compose down/up) |

### 2. BloodHound CE

**Technologie :** Go + PostgreSQL + Neo4j

**Responsabilités :**
- Ingestion des données SharpHound
- Analyse des chemins d'attaque AD
- API REST pour upload et requêtes

**Ports :**
- 8080 : API REST
- 7474 : Interface web Neo4j
- 7687 : Bolt protocol Neo4j

**Intégration avec ToAD :**
```python
# Login
POST /api/v2/login
→ session_token

# Upload SharpHound
POST /api/v2/file-upload/start
POST /api/v2/file-upload/{id}
POST /api/v2/file-upload/{id}/end

# Suivi ingestion
GET /api/v2/jobs
```

### 3. Neo4j

**Technologie :** Neo4j 4.4

**Responsabilités :**
- Base de données graphe pour BloodHound
- Stockage des objets AD et relations
- Requêtes Cypher pour AD-Miner

**Ports :**
- 7474 : Interface web
- 7687 : Bolt protocol

### 4. AD-Miner

**Technologie :** Python

**Responsabilités :**
- Analyse des données Neo4j
- Génération de rapports HTML
- Détection de vulnérabilités AD

**Intégration avec ToAD :**
```python
subprocess.run([
    "python", "-m", "ad_miner",
    "-cf", client_slug,
    "-b", neo4j_url,
    "-u", neo4j_user,
    "-p", neo4j_password,
])
```

### 5. PostgreSQL

**Technologie :** PostgreSQL 16

**Responsabilités :**
- Base de données applicative pour BloodHound
- Stockage des métadonnées BloodHound

**Port :** 5432 (interne, non exposé)

## Flux de données

### Workflow complet d'audit

```
1. Utilisateur
   ↓
2. Upload PingCastle (HTML) + SharpHound (ZIP)
   ↓
3. Archivage fichiers sources
   /data/{slug}/sources/pingcastle/pingcastle_{timestamp}.html
   /data/{slug}/sources/sharphound/sharphound_{timestamp}.zip
   ↓
4. Upload SharpHound → BloodHound API
   POST /api/v2/file-upload/start
   POST /api/v2/file-upload/{id}
   POST /api/v2/file-upload/{id}/end
   ↓
5. BloodHound ingère les données → Neo4j
   (polling GET /api/v2/jobs toutes les 8s)
   ↓
6. Génération AD-Miner
   subprocess: python -m ad_miner -cf {slug} -b bolt://...
   ↓
7. Copie rapport AD-Miner
   /opt/AD_Miner/render_{slug}/ → /data/{slug}/ad-miner/
   ↓
8. Affichage rapports
   PingCastle: /{slug}/pingcastle/index.html
   AD-Miner: /{slug}/ad-miner/index.html
```

### Structure de stockage

```
/data/                                    # ROOT
├── events.log                            # Log système
├── _bloodhound_current.json              # État actuel BloodHound
└── {client-slug}/                        # Un dossier par client
    ├── client.json                       # Métadonnées client
    ├── events.log                        # Log client
    ├── ad-miner/                         # Rapport AD-Miner actuel
    │   └── index.html
    ├── pingcastle/                       # Rapport PingCastle actuel
    │   └── index.html
    └── sources/                          # Archives
        ├── sharphound/                   # ZIP SharpHound archivés
        │   ├── sharphound_20240101_120000.zip
        │   └── sharphound_20240115_143000.zip
        └── pingcastle/                   # HTML PingCastle archivés
            ├── pingcastle_20240101_120000.html
            └── pingcastle_20240115_143000.html
```

## Conteneurisation

### Docker Compose

**Services :**

1. **audit-ad-web** (ToAD)
   - Image : python:3.12-slim
   - Port : 9100:80
   - Volumes :
     - `/srv/audit-ad/web:/src:ro` (code source)
     - `/srv/audit-ad/clients:/data:rw` (données clients)
     - `/opt/AD_Miner:/ad_miner_src:rw` (AD-Miner)
     - `/var/run/docker.sock:/var/run/docker.sock` (Docker-in-Docker)

2. **bloodhound** (BloodHound CE)
   - Image : specterops/bloodhound:latest
   - Port : 8080:8080
   - Dépend de : app-db, graph-db

3. **app-db** (PostgreSQL)
   - Image : postgres:16
   - Volume : postgres-data

4. **graph-db** (Neo4j)
   - Image : neo4j:4.4
   - Ports : 7474:7474, 7687:7687
   - Volume : neo4j-data

### Volumes Docker

- `postgres-data` : Données PostgreSQL BloodHound
- `neo4j-data` : Données Neo4j (graphe AD)
- `/srv/audit-ad/clients` : Données clients (persistantes)
- `/opt/AD_Miner` : Code source AD-Miner

## Sécurité

### Authentification

**Actuel :** Aucune authentification native

**Recommandé :**
- Basic Auth via reverse proxy (nginx/Traefik)
- Ou accès VPN uniquement

### Isolation

- Chaque client a son propre dossier isolé
- Pas de partage de données entre clients
- BloodHound est reset entre audits (évite mélange données)

### Validation

- Slugs : regex `[^a-z0-9_-]` (prévention injection)
- Fichiers : validation extension (.html, .zip)
- Tailles : limites sur uploads (50MB/500MB)
- Paths : protection path traversal (safe_path)

## Performance

### Optimisations actuelles

- `latest_file_date()` : `iterdir()` au lieu de `rglob()` (plus rapide)
- Jobs en arrière-plan : threading (non-bloquant)
- Copie atomique : tmp_dir + rename (évite corruption)

### Limites

- Pas de cache pour `/api/audits` (lecteur filesystem à chaque requête)
- Pas de pagination (tous les clients chargés)
- Pas de streaming pour uploads (fichiers en mémoire)

### Améliorations futures

- Cache Redis pour `/api/audits`
- Pagination des clients
- Streaming uploads
- Indexation des métadonnées (SQLite)

## Extensibilité

### Ajout d'un nouvel outil

1. Créer une fonction d'intégration dans `app.py`
2. Ajouter un endpoint API
3. Ajouter l'interface dans `index.html`
4. Mettre à jour la documentation

### Exemple : Ajout de Certipy

```python
# app.py
@app.post("/api/clients/{slug}/certipy")
def run_certipy(slug: str):
    # Exécuter Certipy
    subprocess.run(["certipy", "find", ...])
    # Stocker résultats
    # Retourner rapport
```

```javascript
// index.html
<button onclick="runCertipy(slug)">Lancer Certipy</button>
```

## Déploiement

### Développement

```bash
docker compose up -d
```

### Production

1. Changer les mots de passe dans `.env`
2. Configurer reverse proxy avec HTTPS
3. Activer authentification
4. Configurer firewall
5. Mettre en place backups

### Scaling

**Actuel :** Single-node

**Futur :**
- Load balancer pour ToAD (stateless)
- Base de données externalisée (SQLite → PostgreSQL)
- Stockage S3 pour fichiers
- Queue pour jobs (Celery/RQ)

## Monitoring

### Logs

- Application : `/data/events.log`
- Docker : `docker logs audit-ad-web`
- BloodHound : `docker logs bloodhound-bloodhound-1`

### Métriques (à implémenter)

- Nombre de clients
- Nombre d'audits par jour
- Temps moyen de génération
- Espace disque utilisé

## Backup

### Données à sauvegarder

- `/srv/audit-ad/clients/` : Données clients (critique)
- `/root/.config/bloodhound/` : Configuration BloodHound
- `.env` : Variables d'environnement

### Script de backup

Voir `scripts/backup.sh`

## Troubleshooting

### Problèmes courants

**BloodHound ne démarre pas :**
```bash
docker compose logs bloodhound
docker compose restart
```

**AD-Miner échoue :**
```bash
docker logs audit-ad-web
# Vérifier connexion Neo4j
```

**Upload échoue :**
```bash
# Vérifier taille fichier
# Vérifier permissions /data
```

---

Pour plus d'informations, voir :
- [README.md](../README.md)
- [docs/security.md](security.md)
- [CONTRIBUTING.md](../CONTRIBUTING.md)
