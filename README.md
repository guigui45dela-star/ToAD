# ToAD - Plateforme d'Audit Active Directory

**Plateforme centralisée pour la gestion et la génération d'audits Active Directory**

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Docker](https://img.shields.io/badge/docker-ready-blue.svg)

## 🎯 Fonctionnalités

- **Centralisation** : Tous vos rapports PingCastle et AD-Miner au même endroit
- **Génération automatique** : Upload SharpHound → BloodHound → AD-Miner en un clic
- **Multi-clients** : Gestion de plusieurs clients avec isolation complète
- **Interface moderne** : UI responsive dark theme, recherche instantanée
- **Rappels intégrés** : Guides procéduraux pour PingCastle, SharpHound, BloodHound
- **Workflow optimisé** : Automatisation complète du processus d'audit

## 🚀 Quick Start

### Prérequis

- Docker & Docker Compose
- 4 Go de RAM minimum (8 Go recommandé)
- Ports disponibles : 9100, 8080, 7474, 7687

### Installation

```bash
# 1. Cloner le repository
git clone https://github.com/your-username/toad.git
cd toad

# 2. Lancer ToAD
docker compose up -d

# 3. Accéder à l'interface de configuration
open http://localhost:9100
```

Au premier démarrage, vous serez automatiquement redirigé vers la page de configuration `/setup`.

### Configuration via l'interface web

ToAD propose deux modes d'installation :

**Mode Local (Recommandé)**
- BloodHound CE, PostgreSQL et Neo4j sont automatiquement déployés
- Configuration simplifiée via l'interface web
- Parfait pour démarrer rapidement

**Mode Remote**
- Connexion à une instance BloodHound existante
- Pour les utilisateurs ayant déjà une infrastructure BloodHound

L'interface de setup vous guide pas à pas :
1. Choix du mode (Local ou Remote)
2. Configuration BloodHound (identifiants, ports)
3. Configuration Neo4j (identifiants, ports)
4. Test des connexions
5. Finalisation et redémarrage automatique

Pour plus de détails, consultez le [Guide d'installation complet](docs/installation.md).

### Utilisation rapide

1. **Audit complet** (recommandé) :
   - Remplir le formulaire "Audit complet"
   - Uploader le rapport PingCastle (HTML)
   - Uploader le ZIP SharpHound
   - L'application gère automatiquement : archivage, import BloodHound, attente ingestion, génération AD-Miner

2. **Actions unitaires** :
   - Créer un client
   - Importer PingCastle séparément
   - Importer SharpHound séparément
   - Générer AD-Miner séparément

## 📸 Screenshots

### Dashboard principal
![Dashboard](docs/screenshots/dashboard.png)

### Actions client
![Client Actions](docs/screenshots/client-actions.png)

### Modal de rappel
![Rappel](docs/screenshots/rappel-modal.png)

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    ToAD (Portail Web)                        │
│  FastAPI Backend + SPA Frontend                              │
│  Port: 9100                                                  │
└──────────────┬──────────────────┬───────────────────────────┘
               │                  │
               ▼                  ▼
┌─────────────────────┐  ┌─────────────────────┐
│   BloodHound CE     │  │     Neo4j DB        │
│   (API REST)        │  │   (Bolt Protocol)   │
│   Port: 8080        │  │   Port: 7687        │
└─────────────────────┘  └─────────────────────┘
               │
               ▼
┌─────────────────────┐
│     AD-Miner        │
│  (Python CLI Tool)  │
│  (Intégré Docker)   │
└─────────────────────┘
```

## ⚙️ Configuration

### Via l'interface web (Recommandé)

La configuration s'effectue via l'interface web `/setup` au premier démarrage :
- Choix du mode (Local ou Remote)
- Configuration des identifiants BloodHound et Neo4j
- Choix des ports
- Test automatique des connexions

### Via fichier .env (Avancé)

Pour une configuration manuelle, copiez `.env.example` vers `.env` et modifiez les variables :

```bash
cp .env.example .env
nano .env
```

Variables principales :
- `BLOODHOUND_MODE` : `local` ou `remote`
- `BLOODHOUND_PASSWORD` : Mot de passe administrateur BloodHound
- `NEO4J_PASSWORD` : Mot de passe Neo4j
- `TOAD_PORT` : Port d'écoute de ToAD (défaut : 9100)

**Variables principales :**

```bash
# BloodHound
BLOODHOUND_URL=http://host.docker.internal:8080
BLOODHOUND_USERNAME=admin
BLOODHOUND_PASSWORD=your-secure-password

# Neo4j
NEO4J_URL=bolt://host.docker.internal:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-secure-password

# ToAD
TOAD_PORT=9100
INGEST_WAIT_SECONDS=30
```

### Personnalisation

**Changer le port d'écoute :**
```bash
TOAD_PORT=8080  # dans .env
```

**Augmenter le timeout d'ingestion :**
```bash
INGEST_WAIT_SECONDS=120  # pour les gros fichiers
```

## 🔒 Sécurité

### Bonnes pratiques

1. **Changez les mots de passe par défaut** dans `.env`
2. **N'exposez pas les ports publiquement** sans authentification
3. **Utilisez un reverse proxy** (nginx, Traefik) avec HTTPS
4. **Activez l'authentification** (voir docs/security.md)
5. **Restreignez l'accès réseau** via firewall (iptables/ufw)

### Authentification

ToAD n'inclut pas d'authentification native par défaut. Options :

**Option 1 : Basic Auth via nginx** (recommandé)
```nginx
location / {
    auth_basic "ToAD Access";
    auth_basic_user_file /etc/nginx/.htpasswd;
    proxy_pass http://localhost:9100;
}
```

**Option 2 : Accès VPN uniquement**
- Déployer ToAD derrière un VPN (WireGuard, OpenVPN)
- Restreindre l'accès aux utilisateurs VPN

Voir [docs/security.md](docs/security.md) pour plus de détails.

## 📚 Documentation

- [Architecture technique](docs/architecture.md)
- [Guide de sécurité](docs/security.md)
- [Guide de contribution](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)

## 🛠️ Développement

### Structure du projet

```
toad/
├── docker-compose.yml      # Orchestration Docker
├── .env.example            # Variables d'environnement
├── web/
│   ├── app.py              # Backend FastAPI
│   └── index.html          # Frontend SPA
├── docs/                   # Documentation
└── scripts/                # Scripts utilitaires
```

### Lancer en développement

```bash
# Backend (FastAPI)
cd web
uvicorn app:app --reload --host 0.0.0.0 --port 8000

# Frontend
# Ouvrir web/index.html dans un navigateur
```

### Tests

```bash
# Lancer les tests (à implémenter)
pytest tests/
```

## 🤝 Contribution

Les contributions sont les bienvenues ! Voir [CONTRIBUTING.md](CONTRIBUTING.md).

### Roadmap

- [ ] Authentification intégrée (JWT/OAuth)
- [ ] Support PDF pour rapports
- [ ] Tags et catégories
- [ ] Comparaison inter-audits
- [ ] API REST documentée (OpenAPI)
- [ ] Plugin system pour nouveaux outils
- [ ] Support Azure AD / Entra ID
- [ ] Multi-utilisateurs avec rôles

## 📄 Licence

MIT License - Voir [LICENSE](LICENSE)

## 🙏 Remerciements

- [BloodHound CE](https://github.com/SpecterOps/BloodHound) - Specter Ops
- [AD-Miner](https://github.com/Mazars-Tech/AD_Miner) - Mazars
- [PingCastle](https://www.pingcastle.com/) - PingCastle
- [SharpHound](https://github.com/BloodHoundAD/SharpHound) - BloodHoundAD

## 📞 Support

- GitHub Issues : [Signaler un bug](https://github.com/votre-username/toad/issues)
- Discussions : [Poser une question](https://github.com/votre-username/toad/discussions)

---

**ToAD** - *Centralisez vos audits Active Directory*
