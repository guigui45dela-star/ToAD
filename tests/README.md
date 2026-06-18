# Tests de Sécurité ToAD

Ce dossier contient les tests de sécurité pour valider les mesures de sécurité implémentées dans ToAD.

## 📋 Tests disponibles

### 1. Tests Python (pytest)

Fichier : `test_security.py`

Tests automatisés avec pytest couvrant :
- Authentification API
- Headers de sécurité
- Rate limiting
- Validation des entrées
- Protection du setup
- Endpoints principaux
- Logging
- Tests d'intégration

#### Exécution

```bash
# Installer pytest
pip install pytest requests

# Exécuter tous les tests
pytest tests/test_security.py -v

# Exécuter avec rapport détaillé
pytest tests/test_security.py -v --tb=short

# Exécuter uniquement les tests d'authentification
pytest tests/test_security.py::TestAuthentication -v
```

### 2. Tests Bash

Fichier : `run_security_tests.sh`

Script bash pour tests rapides sans dépendances Python.

#### Exécution

```bash
# Rendre le script exécutable
chmod +x tests/run_security_tests.sh

# Exécuter les tests
./tests/run_security_tests.sh
```

## 🎯 Ce qui est testé

### Authentification
- ✅ Accès sans token bloqué (401)
- ✅ Accès avec token invalide bloqué (401)
- ✅ Endpoint /api/health accessible sans token
- ✅ Token valide permet l'accès

### Headers de sécurité
- ✅ X-Content-Type-Options: nosniff
- ✅ X-Frame-Options: DENY
- ✅ X-XSS-Protection: 1; mode=block
- ✅ Referrer-Policy: strict-origin-when-cross-origin
- ✅ Content-Security-Policy présent

### Rate limiting
- ✅ Rate limiting activé après 120 requêtes
- ✅ Code HTTP 429 retourné

### Validation des entrées
- ✅ Path traversal bloqué
- ✅ Slugs trop longs rejetés
- ✅ Validation des fichiers uploadés

### Endpoints
- ✅ /api/health fonctionnel
- ✅ /setup accessible
- ✅ / (index) accessible

### Logging
- ✅ Événements loggés dans events.log

## 📊 Résultats attendus

### Environnement de test

Pour exécuter les tests, vous devez avoir :

1. **ToAD démarré**
   ```bash
   docker compose up -d
   ```

2. **Token API configuré**
   
   Dans `.env` :
   ```bash
   API_TOKEN=test-token-for-security-tests-1234567890abcdef
   ```

3. **Redémarrer ToAD**
   ```bash
   docker compose restart
   ```

### Résultats

```
═══════════════════════════════════════════════════════════
  Résumé des tests
═══════════════════════════════════════════════════════════

  Tests effectués : 20
  Tests réussis   : 20
  Tests échoués   : 0

✓ Tous les tests de sécurité sont passés !
✓ ToAD est correctement configuré pour la production.
```

## 🔧 Dépannage

### Erreur : "ToAD n'est pas accessible"

```bash
# Vérifier que ToAD est démarré
docker compose ps

# Vérifier les logs
docker compose logs -f toad-web

# Redémarrer ToAD
docker compose restart
```

### Erreur : "401 Unauthorized"

```bash
# Vérifier que le token est configuré dans .env
grep API_TOKEN .env

# Redémarrer ToAD après modification
docker compose restart
```

### Erreur : "Rate limiting non activé"

Le rate limiting peut être configuré différemment. Vérifiez dans `web/app.py` :

```python
RATE_LIMIT_MAX = 120  # Nombre de requêtes
RATE_LIMIT_WINDOW = 60  # Fenêtre en secondes
```

## 📚 Documentation

- [Guide de configuration sécurisée](../docs/security-configuration.md)
- [Guide de déploiement sécurisé](../docs/deployment-security.md)
- [Audit de sécurité](../SECURITY_AUDIT.md)
- [Politique de sécurité](../SECURITY.md)

## 🤝 Contribution

Pour ajouter de nouveaux tests :

1. Ajoutez les tests dans `test_security.py`
2. Suivez la structure existante (classes par catégorie)
3. Documentez ce que le test vérifie
4. Exécutez tous les tests pour vérifier

## 📝 Notes

- Les tests sont conçus pour être exécutés sur un environnement de test
- Ne pas exécuter en production sans adapter le token API
- Certains tests peuvent échouer si la configuration est différente
- Consultez la documentation pour comprendre chaque mesure de sécurité

---

**Dernière mise à jour :** 17 juin 2026  
**Version :** 1.0.0

---

**ToAD** - *Centralisez vos audits Active Directory* 🐸
