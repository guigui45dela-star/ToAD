# 🔒 Guide de Configuration Sécurisée - ToAD

**Version :** 1.0.0  
**Dernière mise à jour :** 17 juin 2026

---

## 📋 Table des Matières

1. [Introduction](#introduction)
2. [Prérequis](#prérequis)
3. [Configuration des Variables d'Environnement](#configuration-des-variables-denvironnement)
4. [Génération d'un Token API Sécurisé](#génération-dun-token-api-sécurisé)
5. [Configuration de BloodHound](#configuration-de-bloodhound)
6. [Checklist de Sécurité](#checklist-de-sécurité)
7. [Bonnes Pratiques](#bonnes-pratiques)
8. [Dépannage](#dépannage)

---

## Introduction

Ce guide vous aide à configurer ToAD de manière sécurisée pour une utilisation en production. Il couvre la configuration des variables d'environnement, la génération de tokens sécurisés, et les bonnes pratiques de sécurité.

**⚠️ Important :** Ne déployez jamais ToAD en production sans suivre ce guide.

---

## Prérequis

Avant de commencer, assurez-vous d'avoir :

- [x] Docker et Docker Compose installés
- [x] Accès root ou sudo sur le serveur
- [x] Un nom de domaine (recommandé pour HTTPS)
- [x] Un reverse proxy (nginx, Traefik, etc.)
- [x] Certificats SSL/TLS (Let's Encrypt recommandé)

---

## Configuration des Variables d'Environnement

### 1. Copier le fichier d'exemple

```bash
cd /srv/audit-ad
cp .env.example .env
```

### 2. Éditer le fichier .env

```bash
nano .env
```

### 3. Configurer les variables critiques

#### Mode BloodHound

```bash
# Mode local (recommandé pour débuter)
BLOODHOUND_MODE=local

# Mode remote (si vous avez déjà une instance BloodHound)
# BLOODHOUND_MODE=remote
```

#### Ports

```bash
# Port de l'application web
TOAD_PORT=9100

# Port BloodHound (mode local uniquement)
BLOODHOUND_PORT=8080

# Ports Neo4j
NEO4J_WEB_PORT=7474
NEO4J_DB_PORT=7687
```

#### 🔴 CRITIQUE : Mots de passe sécurisés

**Ne JAMAIS utiliser les mots de passe par défaut en production !**

```bash
# Génération de mots de passe sécurisés
BLOODHOUND_PASSWORD=$(openssl rand -base64 32)
NEO4J_PASSWORD=$(openssl rand -base64 32)
POSTGRES_PASSWORD=$(openssl rand -base64 32)
```

Exemple de configuration :

```bash
# BloodHound
BLOODHOUND_USERNAME=admin
BLOODHOUND_PASSWORD=VotreMotDePasseSécuriséIci

# Neo4j
NEO4J_USER=neo4j
NEO4J_PASSWORD=VotreMotDePasseSécuriséIci

# PostgreSQL
POSTGRES_USER=bloodhound
POSTGRES_PASSWORD=VotreMotDePasseSécuriséIci
POSTGRES_DB=bloodhound
```

#### 🔴 CRITIQUE : Token API

```bash
# Générer un token sécurisé
API_TOKEN=$(openssl rand -hex 32)
```

Exemple :

```bash
API_TOKEN=a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6
```

**⚠️ Important :** Conservez ce token en lieu sûr. Il sera nécessaire pour accéder à l'API.

#### Configuration avancée

```bash
# Temps d'attente pour l'ingestion BloodHound (secondes)
INGEST_WAIT_SECONDS=30

# Fuseau horaire
TZ=Europe/Paris
```

### 4. Sécuriser le fichier .env

```bash
# Restreindre les permissions
chmod 600 .env

# Vérifier les permissions
ls -l .env
# Devrait afficher : -rw------- 1 root root ...
```

---

## Génération d'un Token API Sécurisé

### Méthode 1 : OpenSSL (Recommandé)

```bash
openssl rand -hex 32
```

Exemple de sortie :

```
a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6
```

### Méthode 2 : Python

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### Méthode 3 : En ligne de commande

```bash
cat /dev/urandom | tr -dc 'a-zA-Z0-9' | fold -w 64 | head -n 1
```

### Utilisation du Token

Une fois le token généré, ajoutez-le dans votre fichier `.env` :

```bash
API_TOKEN=votre_token_genere
```

Pour utiliser l'API, ajoutez le header `Authorization` :

```bash
curl -H "Authorization: Bearer votre_token_genere" \
  http://localhost:9100/api/audits
```

---

## Configuration de BloodHound

### Mode Local

Si vous utilisez `BLOODHOUND_MODE=local`, ToAD gère automatiquement BloodHound.

**Configuration recommandée :**

```bash
BLOODHOUND_MODE=local
BLOODHOUND_PORT=8080
NEO4J_WEB_PORT=7474
NEO4J_DB_PORT=7687
```

### Mode Remote

Si vous utilisez une instance BloodHound existante :

```bash
BLOODHOUND_MODE=remote
BLOODHOUND_URL=http://votre-bloodhound:8080
BLOODHOUND_USERNAME=admin
BLOODHOUND_PASSWORD=votre_mot_de_passe
NEO4J_URL=bolt://votre-neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=votre_mot_de_passe
```

---

## Checklist de Sécurité

Avant de mettre ToAD en production, vérifiez :

### 🔴 Critique

- [ ] Mots de passe BloodHound, Neo4j et PostgreSQL changés
- [ ] Token API généré et configuré
- [ ] Fichier `.env` avec permissions 600
- [ ] Reverse proxy configuré avec HTTPS
- [ ] Firewall configuré (voir guide de déploiement)

### 🟡 Important

- [ ] Documentation lue et comprise
- [ ] Tests effectués en environnement de test
- [ ] Backup configuré
- [ ] Monitoring en place
- [ ] Logs vérifiés

### 🟢 Recommandé

- [ ] Rate limiting ajusté selon vos besoins
- [ ] Headers de sécurité vérifiés
- [ ] Certificats SSL/TLS valides
- [ ] Documentation interne créée

---

## Bonnes Pratiques

### 1. Gestion des Secrets

- ✅ Utilisez des variables d'environnement
- ✅ Ne commitez jamais `.env` dans Git
- ✅ Rotations régulières des mots de passe (tous les 90 jours)
- ✅ Utilisez un gestionnaire de secrets (Vault, AWS Secrets Manager)

### 2. Réseau

- ✅ Exposez uniquement le port ToAD (9100) via reverse proxy
- ✅ BloodHound et Neo4j en réseau interne uniquement
- ✅ Utilisez HTTPS pour toutes les communications
- ✅ Configurez un firewall restrictif

### 3. Authentification

- ✅ Utilisez un token API fort (64 caractères minimum)
- ✅ Rotations régulières du token
- ✅ Limitez les accès IP si possible
- ✅ Audit régulier des accès

### 4. Monitoring

- ✅ Surveillez les logs d'authentification
- ✅ Alertes sur les tentatives d'accès échouées
- ✅ Monitoring des performances
- ✅ Backup automatique des données

### 5. Mises à Jour

- ✅ Gardez ToAD à jour
- ✅ Mettez à jour les dépendances régulièrement
- ✅ Surveillez les advisories de sécurité
- ✅ Testez les mises à jour en environnement de test

---

## Dépannage

### Problème : "Unauthorized" lors de l'accès à l'API

**Cause :** Token API manquant ou incorrect

**Solution :**

```bash
# Vérifier que le token est configuré
grep API_TOKEN .env

# Vérifier le header dans la requête
curl -H "Authorization: Bearer $API_TOKEN" http://localhost:9100/api/health
```

### Problème : BloodHound ne démarre pas

**Cause :** Ports déjà utilisés ou configuration incorrecte

**Solution :**

```bash
# Vérifier les ports utilisés
netstat -tulpn | grep -E '8080|7474|7687'

# Vérifier les logs
docker logs toad-bloodhound

# Redémarrer BloodHound
docker compose restart toad-bloodhound
```

### Problème : Impossible de se connecter à Neo4j

**Cause :** Mot de passe incorrect ou service non démarré

**Solution :**

```bash
# Vérifier que Neo4j est démarré
docker ps | grep neo4j

# Vérifier les logs
docker logs toad-graph-db

# Réinitialiser le mot de passe (attention : perte de données)
docker compose down -v
docker compose up -d
```

### Problème : Rate limiting trop restrictif

**Cause :** Limite de 120 requêtes/minute trop basse

**Solution :**

Modifier dans `web/app.py` :

```python
RATE_LIMIT_MAX = 200  # Augmenter la limite
RATE_LIMIT_WINDOW = 60  # Fenêtre de 60 secondes
```

Puis redémarrer :

```bash
docker compose restart toad-web
```

---

## Ressources Supplémentaires

- [Guide de Déploiement Sécurisé](deployment-security.md)
- [Documentation API](api-documentation.md)
- [Politique de Sécurité](../SECURITY.md)
- [Audit de Sécurité](../SECURITY_AUDIT.md)

---

## Support

Si vous rencontrez des problèmes de sécurité :

1. Consultez la documentation
2. Vérifiez les logs (`docker logs toad-web`)
3. Consultez les issues GitHub
4. Ouvrez une issue avec le label "security"

**⚠️ Important :** Ne partagez jamais vos mots de passe ou tokens dans les issues publiques.

---

**Dernière mise à jour :** 17 juin 2026  
**Version :** 1.0.0

---

**ToAD** - *Centralisez vos audits Active Directory* 🐸
