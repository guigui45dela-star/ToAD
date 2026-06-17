<div align="center">

<img src="docs/assets/logo.png" alt="ToAD Logo" width="200"/>

# 🐸 ToAD - Plateforme d'Audit Active Directory

**Plateforme centralisée pour la gestion et la génération d'audits Active Directory**

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/guigui45dela-star/ToAD/releases)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](http://makeapullrequest.com)

**[Français](README.md)** | **[English](README.en.md)**

[Installation](#-installation) • [Documentation](#-documentation) • [Contribuer](#-contribuer) • [Support](#-support)

</div>

---

## 📖 Table des Matières

- [Fonctionnalités](#-fonctionnalités)
- [Installation](#-installation)
- [Configuration](#-configuration)
- [Utilisation](#-utilisation)
- [Architecture](#-architecture)
- [Sécurité](#-sécurité)
- [Documentation](#-documentation)
- [Contribuer](#-contribuer)
- [Roadmap](#-roadmap)
- [Support](#-support)
- [Licence](#-licence)
- [Remerciements](#-remerciements)

---

## 🎯 Fonctionnalités

- **Centralisation** : Tous vos rapports PingCastle et AD-Miner au même endroit
- **Génération automatique** : Upload SharpHound → BloodHound → AD-Miner en un clic
- **Multi-clients** : Gestion de plusieurs clients avec isolation complète
- **Interface moderne** : UI responsive dark theme, recherche instantanée
- **Rappels intégrés** : Guides procéduraux pour PingCastle, SharpHound, BloodHound
- **Workflow optimisé** : Automatisation complète du processus d'audit

## 🚀 Installation

### Prérequis

- Docker & Docker Compose
- 4 Go de RAM minimum (8 Go recommandé)
- Ports disponibles : 9100, 8080, 7474, 7687

### Installation Rapide

```bash
# 1. Cloner le repository
git clone https://github.com/guigui45dela-star/ToAD.git
cd ToAD

# 2. Lancer ToAD
docker compose up -d

# 3. Accéder à l'interface de configuration
open http://localhost:9100
```

Au premier démarrage, vous serez automatiquement redirigé vers la page de configuration `/setup`.

### Installation Détaillée

Pour une installation complète avec configuration manuelle, consultez le [Guide d'Installation](docs/installation.md).

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

## 🤝 Contribuer

Les contributions sont les bienvenues ! Consultez [CONTRIBUTING.md](CONTRIBUTING.md) pour commencer.

### Comment contribuer

1. **Fork** le projet
2. Créez une branche (`git checkout -b feature/AmazingFeature`)
3. **Commit** vos changements (`git commit -m 'Add: AmazingFeature'`)
4. **Push** vers la branche (`git push origin feature/AmazingFeature`)
5. Ouvrez une **Pull Request**

### Types de contributions

- 🐛 **Bug fixes** - Corriger des bugs existants
- ✨ **Nouvelles fonctionnalités** - Ajouter des fonctionnalités
- 📚 **Documentation** - Améliorer la documentation
- 🎨 **UI/UX** - Améliorer l'interface utilisateur
- 🔒 **Sécurité** - Signaler ou corriger des vulnérabilités
- 🧪 **Tests** - Ajouter des tests automatisés

Merci à tous les contributeurs ! 🙏

## 🗺️ Roadmap

### Version 1.1 (Q3 2026)
- [ ] Authentification intégrée (JWT/OAuth)
- [ ] Support PDF pour rapports
- [ ] Tags et catégories

### Version 1.2 (Q4 2026)
- [ ] Comparaison inter-audits
- [ ] API REST documentée (OpenAPI)
- [ ] Notifications (Slack, Teams)

### Version 2.0 (2027)
- [ ] Plugin system pour nouveaux outils
- [ ] Support Azure AD / Entra ID
- [ ] Multi-utilisateurs avec rôles
- [ ] Dashboard comparatif multi-clients

Consultez les [Issues GitHub](https://github.com/guigui45dela-star/ToAD/issues) pour voir toutes les fonctionnalités planifiées.

## 📄 Licence

Distribué sous licence MIT. Voir [LICENSE](LICENSE) pour plus d'informations.

```
MIT License

Copyright (c) 2026 ToAD Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction...
```

## 🙏 Remerciements

ToAD repose sur des outils open-source exceptionnels :

- **[BloodHound CE](https://github.com/SpecterOps/BloodHound)** - Specter Ops
  - Analyse des chemins d'attaque Active Directory
  
- **[AD-Miner](https://github.com/Mazars-Tech/AD_Miner)** - Mazars
  - Génération de rapports d'audit AD
  
- **[PingCastle](https://www.pingcastle.com/)** - PingCastle
  - Évaluation de la sécurité Active Directory
  
- **[SharpHound](https://github.com/BloodHoundAD/SharpHound)** - BloodHoundAD
  - Collecte de données AD pour BloodHound

Merci à toutes les communautés qui maintiennent ces outils !

## 📞 Support

### Obtenir de l'aide

- 📖 **Documentation** : [docs/](docs/)
- 🐛 **Signaler un bug** : [GitHub Issues](https://github.com/guigui45dela-star/ToAD/issues)
- 💬 **Discussions** : [GitHub Discussions](https://github.com/guigui45dela-star/ToAD/discussions)
- 🔒 **Sécurité** : [SECURITY.md](SECURITY.md)

### Ressources utiles

- [Guide d'installation](docs/installation.md)
- [Guide de sécurité](docs/security.md)
- [Architecture technique](docs/architecture.md)
- [Guide de migration](docs/migration.md)

## ⭐ Soutenir le projet

Si ToAD vous est utile, n'hésitez pas à :

- ⭐ **Starrer** le repository
- 🍴 **Forker** et contribuer
- 📢 **Partager** avec votre réseau
- 🐛 **Signaler** les bugs
- 💡 **Suggérer** des améliorations

---

<div align="center">

**Fait avec ❤️ par la communauté cybersécurité**

[🐸 ToAD](https://github.com/guigui45dela-star/ToAD) - *Centralisez vos audits Active Directory*

[Installation](#-installation) • [Documentation](#-documentation) • [Contribuer](#-contribuer) • [Support](#-support)

</div>
