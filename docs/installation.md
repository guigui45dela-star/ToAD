# Guide d'installation ToAD

Ce guide vous accompagne pas à pas dans l'installation de ToAD, de la préparation à la première utilisation.

## Prérequis

### Système

- **OS** : Linux (Ubuntu 20.04+, Debian 11+, CentOS 8+) ou macOS
- **RAM** : Minimum 4 Go (8 Go recommandé)
- **Disk** : Minimum 10 Go d'espace libre
- **CPU** : 2 cores minimum

### Logiciels

- **Docker** : Version 20.10 ou supérieure
- **Docker Compose** : Version 2.0 ou supérieure

Vérifiez votre installation :

```bash
docker --version
docker compose version
```

### Ports requis

ToAD utilise les ports suivants :

| Port | Service | Description |
|------|---------|-------------|
| 9100 | ToAD | Interface web principale |
| 8080 | BloodHound | API BloodHound CE |
| 7474 | Neo4j | Interface web Neo4j |
| 7687 | Neo4j | Bolt protocol Neo4j |

Assurez-vous que ces ports sont disponibles :

```bash
sudo lsof -i :9100
sudo lsof -i :8080
sudo lsof -i :7474
sudo lsof -i :7687
```

## Installation

### Étape 1 : Cloner le repository

```bash
git clone https://github.com/your-username/toad.git
cd toad
```

### Étape 2 : Configuration initiale

ToAD propose deux modes d'installation :

#### Mode Local (Recommandé)

BloodHound CE, PostgreSQL et Neo4j sont automatiquement déployés avec ToAD. C'est le mode le plus simple pour démarrer.

#### Mode Remote

Connectez-vous à une instance BloodHound existante. Utile si vous avez déjà une infrastructure BloodHound en place.

### Étape 3 : Lancer ToAD

```bash
docker compose up -d
```

Au premier démarrage, ToAD va :
1. Construire l'image Docker (installation d'AD-Miner et des dépendances)
2. Démarrer les services (ToAD, BloodHound, PostgreSQL, Neo4j)
3. Attendre que tous les services soient opérationnels

Ce processus peut prendre 5 à 10 minutes lors du premier lancement.

Vérifiez que tous les conteneurs sont démarrés :

```bash
docker compose ps
```

Vous devriez voir 4 conteneurs avec le statut "Up" :
- toad-web
- toad-bloodhound
- toad-app-db
- toad-graph-db

### Étape 4 : Configuration via l'interface web

Accédez à ToAD via votre navigateur :

```
http://localhost:9100
```

Vous serez automatiquement redirigé vers la page de configuration `/setup`.

#### Configuration pas à pas

**Étape 1 : Choix du mode**

Sélectionnez le mode d'installation :
- **Local** : BloodHound est géré par ToAD (recommandé)
- **Remote** : Connexion à un BloodHound existant

**Étape 2 : Configuration BloodHound**

*Mode Local :*
- Définissez un nom d'utilisateur administrateur (par défaut : `admin`)
- Créez un mot de passe sécurisé (12+ caractères)
- Choisissez le port BloodHound (par défaut : `8080`)

*Mode Remote :*
- Entrez l'URL de votre instance BloodHound
- Fournissez les identifiants administrateur

**Étape 3 : Configuration Neo4j**

*Mode Local :*
- Définissez un nom d'utilisateur Neo4j (par défaut : `neo4j`)
- Créez un mot de passe sécurisé
- Choisissez les ports Neo4j (par défaut : `7474` et `7687`)

*Mode Remote :*
- Entrez l'URL Bolt de votre instance Neo4j
- Fournissez les identifiants Neo4j

**Étape 4 : Test des connexions**

Cliquez sur "Tester les connexions" pour vérifier que ToAD peut communiquer avec BloodHound et Neo4j.

Si les tests échouent :
- Vérifiez que les ports sont corrects
- Vérifiez que les services sont bien démarrés (`docker compose ps`)
- Consultez les logs : `docker compose logs`

**Étape 5 : Finalisation**

Cliquez sur "Finaliser l'installation". ToAD va :
1. Sauvegarder la configuration
2. Créer le fichier marker d'installation
3. Redémarrer automatiquement

Après le redémarrage, vous serez redirigé vers l'interface principale de ToAD.

## Première utilisation

### Créer votre premier client

1. Cliquez sur "Nouveau client"
2. Entrez le nom du client (ex: "ACME Corporation")
3. Entrez un slug (ex: "acme")
4. Cliquez sur "Créer"

### Importer un rapport PingCastle

1. Cliquez sur le client créé
2. Dans la section "Importer PingCastle", sélectionnez votre fichier HTML
3. Cliquez sur "Importer"
4. Le rapport est maintenant accessible via l'onglet "PingCastle"

### Importer des données SharpHound et générer AD-Miner

1. Cliquez sur le client
2. Dans la section "Importer SharpHound", sélectionnez votre fichier ZIP
3. Cliquez sur "Importer"
4. ToAD va automatiquement :
   - Envoyer les données à BloodHound
   - Attendre l'ingestion
   - Générer le rapport AD-Miner
5. Une fois terminé, le rapport AD-Miner est accessible via l'onglet "AD-Miner"

## Mode Remote (BloodHound existant)

Si vous utilisez une instance BloodHound existante :

### Prérequis

- BloodHound CE doit être accessible depuis le serveur ToAD
- Vous devez avoir les identifiants administrateur
- Neo4j doit être accessible via le protocole Bolt

### Configuration

Lors du setup, sélectionnez "Mode Remote" et fournissez :
- URL BloodHound (ex: `http://bloodhound.example.com:8080`)
- Identifiants BloodHound
- URL Neo4j Bolt (ex: `bolt://neo4j.example.com:7687`)
- Identifiants Neo4j

### docker-compose.remote.yml

Si vous préférez utiliser un fichier docker-compose dédié :

```bash
docker compose -f docker-compose.remote.yml up -d
```

Ce fichier ne démarre que ToAD, sans BloodHound ni Neo4j.

## Maintenance

### Sauvegarde

Les données clients sont stockées dans le dossier `clients/`. Sauvegardez régulièrement ce dossier :

```bash
tar -czf toad-backup-$(date +%Y%m%d).tar.gz clients/
```

### Mise à jour

```bash
git pull origin main
docker compose down
docker compose build
docker compose up -d
```

### Logs

Consultez les logs en temps réel :

```bash
docker compose logs -f toad-web
```

Logs de tous les services :

```bash
docker compose logs -f
```

### Redémarrage

```bash
docker compose restart
```

## Dépannage

### ToAD ne démarre pas

Vérifiez les logs :

```bash
docker compose logs toad-web
```

Erreurs courantes :
- **Port déjà utilisé** : Changez le port dans `.env`
- **Permission refusée** : Vérifiez les permissions Docker
- **Mémoire insuffisante** : Augmentez la RAM disponible

### BloodHound ne démarre pas

```bash
docker compose logs toad-bloodhound
```

Solutions :
- Vérifiez que les ports 8080, 7474, 7687 sont libres
- Vérifiez que PostgreSQL et Neo4j sont bien démarrés
- Redémarrez les services : `docker compose restart toad-bloodhound toad-app-db toad-graph-db`

### Impossible d'accéder à l'interface web

- Vérifiez que le conteneur toad-web est démarré
- Vérifiez que le port 9100 est accessible
- Essayez un autre navigateur
- Videz le cache du navigateur

### Les rapports AD-Miner ne se génèrent pas

Vérifiez les logs :

```bash
docker compose logs toad-web | grep "AD-Miner"
```

Causes possibles :
- Neo4j n'est pas accessible
- Les données SharpHound n'ont pas été ingérées
- AD-Miner n'est pas correctement installé

Solutions :
- Vérifiez que BloodHound a bien ingéré les données
- Vérifiez la connexion Neo4j
- Redémarrez ToAD : `docker compose restart`

### Erreur "Setup incomplet"

Si vous êtes bloqué sur la page de setup :

1. Vérifiez que le fichier `clients/config/installed.flag` existe
2. Si non, complétez le setup via l'interface web
3. Si le problème persiste, redémarrez ToAD : `docker compose restart`

## Sécurité

### Bonnes pratiques

1. **Changez les mots de passe par défaut** lors de l'installation
2. **N'exposez pas les ports publiquement** sans authentification
3. **Utilisez un reverse proxy** (nginx, Traefik) avec HTTPS
4. **Activez l'authentification** (voir docs/security.md)
5. **Restreignez l'accès réseau** via firewall

### Firewall

Exemple avec UFW :

```bash
sudo ufw allow 9100/tcp  # ToAD
sudo ufw allow 8080/tcp  # BloodHound
sudo ufw allow 7474/tcp  # Neo4j Web
sudo ufw allow 7687/tcp  # Neo4j Bolt
sudo ufw enable
```

**Recommandation** : N'exposez que le port 9100 (ToAD) et utilisez un reverse proxy pour les autres services.

## Support

- **Documentation** : Consultez le dossier `docs/`
- **Issues** : https://github.com/your-username/toad/issues
- **Discussions** : https://github.com/your-username/toad/discussions

## Licence

MIT License - Voir LICENSE
