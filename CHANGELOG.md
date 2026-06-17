# Changelog

Tous les changements notables de ce projet seront documentés dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/),
et ce projet adhère au [Semantic Versioning](https://semver.org/lang/fr/).

## [1.0.0] - 2024-XX-XX

### Ajouté

- **Interface web complète**
  - Dashboard principal avec liste des clients
  - Système de recherche instantanée
  - Indicateurs visuels (statut rapports)
  - Design responsive dark theme
  
- **Gestion multi-clients**
  - Création de clients (nom + slug)
  - Suppression de clients
  - Isolation complète des données par client
  
- **Import PingCastle**
  - Upload de rapports HTML
  - Archivage automatique avec timestamp
  - Affichage du rapport actuel
  
- **Intégration BloodHound CE**
  - Upload automatique des ZIP SharpHound
  - Suivi de l'ingestion en temps réel
  - Reset de BloodHound entre audits
  
- **Génération AD-Miner**
  - Génération automatique après ingestion BloodHound
  - Stockage des rapports générés
  - Accès direct aux rapports HTML
  
- **Workflow complet**
  - Audit complet en une seule opération
  - Actions unitaires (import PingCastle, SharpHound, génération AD-Miner)
  - Système de jobs en arrière-plan avec progression
  
- **Rappels intégrés**
  - Guide de procédure complète (portail)
  - Guide PingCastle (commandes, fichiers)
  - Guide SharpHound Windows (préparation, collecte, AV)
  - Guide SharpHound Linux (bloodhound-python)
  - Guide VM Hyper-V (template, jonction domaine)
  - Guide gestion antivirus (Defender, ESET, Bitdefender)
  
- **Téléchargement sources**
  - Liste des fichiers SharpHound archivés
  - Téléchargement des ZIP sources
  
- **Documentation**
  - README bilingue (FR/EN)
  - Guide d'architecture
  - Guide de sécurité
  - Guide de contribution
  - Changelog
  
- **Scripts utilitaires**
  - Script d'installation automatique
  - Script de backup
  - Script de restauration
  
- **Sécurité**
  - Validation des slugs (prévention path traversal)
  - Protection contre path traversal dans safe_path()
  - Limites de taille sur les uploads (50MB PingCastle, 500MB SharpHound)
  - Confirmations avant actions destructives
  - Variables d'environnement pour credentials
  
- **Optimisations**
  - Optimisation de latest_file_date() (iterdir au lieu de rglob)
  - Restart policy pour conteneurs BloodHound
  - Gestion des erreurs avec messages informatifs

### Technique

- **Backend** : FastAPI (Python 3.12)
- **Frontend** : Vanilla HTML/CSS/JS (SPA)
- **Base de données** : Neo4j 4.4 (BloodHound)
- **API BloodHound** : REST API v2
- **Conteneurisation** : Docker + Docker Compose
- **Outils AD** : BloodHound CE, AD-Miner, PingCastle, SharpHound

---

## [Unreleased]

### À venir

- Authentification intégrée (JWT/OAuth)
- Support PDF pour rapports
- Tags et catégories pour audits
- Comparaison inter-audits (évolution dans le temps)
- API REST documentée (OpenAPI/Swagger)
- Plugin system pour nouveaux outils
- Support Azure AD / Entra ID
- Multi-utilisateurs avec rôles
- Export/import de clients (backup portable)
- Notifications (Slack, Teams, email)
- Dashboard comparatif multi-clients
- Recherche fulltext dans les rapports

---

## Notes de version

### 1.0.0 - Version initiale

Première version publique de ToAD, basée sur l'outil interne utilisé pour les audits AD.

**Fonctionnalités principales :**
- Centralisation des rapports PingCastle et AD-Miner
- Génération automatique de rapports AD-Miner via BloodHound
- Interface web moderne et responsive
- Gestion multi-clients
- Rappels procéduraux intégrés

**Objectif :**
Fournir une plateforme simple et efficace pour centraliser et générer des audits Active Directory.
