# Migration vers ToAD v1.0

Ce guide explique comment migrer depuis l'ancienne version de ToAD (audit-ad-web) vers la nouvelle version unifiée.

## Contexte

L'ancienne version utilisait :
- Un conteneur `audit-ad-web` séparé
- BloodHound installé manuellement dans `~/.config/bloodhound/`
- AD-Miner installé manuellement dans `/opt/AD_Miner/`

La nouvelle version intègre tout dans un seul docker-compose avec :
- Installation automatique d'AD-Miner dans l'image Docker
- BloodHound CE déployé automatiquement (mode local)
- Configuration via interface web `/setup`

## Prérequis

- Docker et Docker Compose installés
- Accès à l'ancienne installation
- Sauvegarde des données clients

## Procédure de migration

### Étape 1 : Sauvegarder les données

Avant toute chose, sauvegardez vos données clients :

```bash
# Sauvegarder les données clients
tar -czf toad-migration-backup-$(date +%Y%m%d).tar.gz clients/

# Sauvegarder l'ancien .env si existe
cp .env .env.old 2>/dev/null || true
```

### Étape 2 : Arrêter l'ancienne installation

```bash
# Arrêter l'ancien conteneur
docker stop audit-ad-web
docker rm audit-ad-web

# Arrêter BloodHound si nécessaire
cd ~/.config/bloodhound
docker compose down
cd -
```

### Étape 3 : Cloner la nouvelle version

```bash
# Sauvegarder l'ancien dossier si nécessaire
mv audit-ad audit-ad.old

# Cloner la nouvelle version
git clone https://github.com/your-username/toad.git
cd toad
```

### Étape 4 : Restaurer les données clients

```bash
# Copier les données clients
cp -r ../audit-ad.old/clients ./

# Ou extraire depuis la sauvegarde
tar -xzf toad-migration-backup-*.tar.gz
```

### Étape 5 : Configuration

Lancez ToAD pour la première fois :

```bash
docker compose up -d
```

Accédez à l'interface web :

```
http://localhost:9100
```

Vous serez redirigé vers `/setup`.

### Étape 6 : Configuration via /setup

**Si vous voulez réutiliser votre ancienne instance BloodHound :**

1. Sélectionnez "Mode Remote"
2. Entrez l'URL de votre BloodHound (ex: `http://localhost:8080`)
3. Entrez les identifiants BloodHound
4. Entrez l'URL Neo4j (ex: `bolt://localhost:7687`)
5. Entrez les identifiants Neo4j

**Si vous voulez utiliser la nouvelle installation tout-en-un :**

1. Sélectionnez "Mode Local"
2. Définissez les nouveaux mots de passe
3. ToAD va démarrer automatiquement BloodHound, PostgreSQL et Neo4j

### Étape 7 : Vérification

Vérifiez que tous vos clients sont présents :

```bash
ls clients/
```

Accédez à l'interface web et vérifiez que :
- Tous les clients sont listés
- Les rapports PingCastle sont accessibles
- Les rapports AD-Miner sont accessibles
- BloodHound est accessible (si mode local)

### Étape 8 : Nettoyage (optionnel)

Une fois la migration vérifiée, vous pouvez supprimer l'ancienne installation :

```bash
rm -rf ../audit-ad.old
rm toad-migration-backup-*.tar.gz
```

## Différences avec l'ancienne version

### Architecture

| Ancienne version | Nouvelle version |
|------------------|------------------|
| Conteneur séparé `audit-ad-web` | Conteneur unifié `toad-web` |
| BloodHound manuel dans `~/.config/bloodhound/` | BloodHound automatique (mode local) |
| AD-Miner manuel dans `/opt/AD_Miner/` | AD-Miner dans l'image Docker |
| Configuration manuelle dans `.env` | Configuration via `/setup` |
| Ports fixes | Ports configurables |

### Ports

| Service | Ancien port | Nouveau port |
|---------|-------------|--------------|
| ToAD | 9100 | 9100 (configurable) |
| BloodHound | 8080 | 8080 (configurable) |
| Neo4j Web | 7474 | 7474 (configurable) |
| Neo4j Bolt | 7687 | 7687 (configurable) |

### Configuration

**Ancienne méthode :**
```bash
# Configuration manuelle dans .env
BLOODHOUND_PASSWORD=xxx
NEO4J_PASSWORD=xxx
```

**Nouvelle méthode :**
```bash
# Configuration via interface web /setup
# Ou édition manuelle de .env après setup
```

## Dépannage

### Les clients n'apparaissent pas

Vérifiez que le dossier `clients/` est bien monté :

```bash
docker compose exec toad-web ls /data
```

### BloodHound n'est pas accessible

Si vous utilisez le mode remote, vérifiez que votre ancienne instance BloodHound est toujours démarrée :

```bash
cd ~/.config/bloodhound
docker compose up -d
```

### AD-Miner ne fonctionne pas

AD-Miner est maintenant intégré dans l'image Docker. Vérifiez qu'il est bien installé :

```bash
docker compose exec toad-web ls /opt/AD_Miner
```

## Support

Si vous rencontrez des problèmes lors de la migration :

1. Consultez les logs : `docker compose logs`
2. Vérifiez la documentation : `docs/installation.md`
3. Ouvrez une issue : https://github.com/your-username/toad/issues

---

**Note** : La migration est réversible. Vous pouvez toujours revenir à l'ancienne version en restaurant `audit-ad.old`.
