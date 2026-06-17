# 🌿 Guide des Branches et Workflow Git

Ce document décrit les conventions de branches et le workflow Git utilisé pour le projet ToAD.

## 📋 Table des matières

- [Branches principales](#-branches-principales)
- [Branches de développement](#-branches-de-développement)
- [Conventions de nommage](#-conventions-de-nommage)
- [Workflow de contribution](#-workflow-de-contribution)
- [Règles de protection](#-règles-de-protection)
- [Bonnes pratiques](#-bonnes-pratiques)

---

## 🏠 Branches principales

### `main` (protégée)
- **Statut** : ✅ Production
- **Protection** : Push direct interdit
- **Usage** : Code stable et déployé
- **Règles** :
  - Uniquement via Pull Requests
  - Requiert au moins 1 review
  - Les checks CI doivent passer
  - Historique linéaire obligatoire

### `develop` (recommandée)
- **Statut** : 🚧 Développement
- **Usage** : Intégration des fonctionnalités
- **Règles** :
  - Push direct interdit (recommandé)
  - Base pour les branches de features
  - Merge vers `main` pour les releases

---

## 🔧 Branches de développement

### Branches de fonctionnalités (`feature/*`)
```
feature/nom-de-la-fonctionnalite
```

**Exemples :**
- `feature/add-authentication`
- `feature/pdf-reports`
- `feature/dark-mode`

**Règles :**
- Basée sur `develop` (ou `main` si `develop` n'existe pas)
- Nommage en anglais, kebab-case
- Doit être mergée via PR
- Supprimée après merge

### Branches de correction (`fix/*` ou `bugfix/*`)
```
fix/description-du-bug
bugfix/issue-123-login-error
```

**Exemples :**
- `fix/upload-timeout`
- `bugfix/issue-42-crash-on-startup`

**Règles :**
- Basée sur `develop` ou `main` (hotfix)
- Référencer l'issue si applicable
- Doit être mergée via PR

### Branches de release (`release/*`)
```
release/v1.2.0
```

**Exemples :**
- `release/v1.1.0`
- `release/v2.0.0-beta`

**Règles :**
- Basée sur `develop`
- Utilisée pour préparer une release
- Corrections de bugs uniquement (pas de nouvelles features)
- Mergée vers `main` ET `develop`

### Branches hotfix (`hotfix/*`)
```
hotfix/description-critique
```

**Exemples :**
- `hotfix/security-vulnerability`
- `hotfix/crash-on-startup`

**Règles :**
- Basée sur `main`
- Pour corrections urgentes en production
- Mergée vers `main` ET `develop`

---

## 📝 Conventions de nommage

### Format général
```
<type>/<description-courte>
```

### Types autorisés
- `feature/` - Nouvelle fonctionnalité
- `fix/` - Correction de bug
- `bugfix/` - Correction de bug (alternative)
- `hotfix/` - Correction urgente
- `release/` - Préparation de release
- `docs/` - Documentation uniquement
- `refactor/` - Refactorisation
- `test/` - Tests uniquement
- `chore/` - Tâches de maintenance

### Règles de nommage
1. **En anglais** (sauf si équipe francophone uniquement)
2. **Kebab-case** : mots séparés par des tirets
3. **Court mais descriptif** : max 50 caractères
4. **Pas d'espaces** ni caractères spéciaux
5. **Référencer l'issue** si applicable : `feature/issue-123-add-auth`

### Exemples ✅
```
feature/add-oauth-authentication
fix/memory-leak-in-worker
bugfix/issue-42-crash-on-startup
hotfix/security-xss-vulnerability
release/v1.2.0
docs/update-installation-guide
refactor/simplify-api-client
test/add-unit-tests-for-auth
chore/update-dependencies
```

### Exemples ❌
```
ma-branche                    # Pas de type
feature/Ma Branche            # Espaces et majuscules
feature/add_feature           # Underscore au lieu de tiret
feature/ajout-authentification # Français (sauf si convenu)
wip                           # Pas descriptif
```

---

## 🔄 Workflow de contribution

### 1. Créer une branche

```bash
# S'assurer d'être à jour
git checkout develop
git pull origin develop

# Créer une nouvelle branche
git checkout -b feature/ma-fonctionnalite
```

### 2. Développer

```bash
# Faire des commits réguliers et descriptifs
git add .
git commit -m "feat: add authentication form"
git commit -m "test: add unit tests for auth"
git commit -m "docs: update README with auth info"
```

### 3. Synchroniser

```bash
# Récupérer les changements de develop
git fetch origin
git rebase origin/develop

# Résoudre les conflits si nécessaire
git rebase --continue
```

### 4. Pousser

```bash
# Pousser la branche
git push -u origin feature/ma-fonctionnalite
```

### 5. Créer une Pull Request

1. Aller sur GitHub
2. Cliquer sur "Compare & pull request"
3. Remplir le template de PR
4. Assigner des reviewers
5. Attendre les reviews

### 6. Corrections (si nécessaire)

```bash
# Faire les corrections demandées
git add .
git commit -m "fix: address review comments"
git push
```

### 7. Merge

Une fois approuvée :
- Le maintainer merge la PR
- La branche est supprimée automatiquement
- Synchroniser sa branche locale

```bash
git checkout develop
git pull origin develop
git branch -d feature/ma-fonctionnalite
```

---

## 🔒 Règles de protection

### Branche `main`

| Règle | Valeur |
|-------|--------|
| Push direct | ❌ Interdit |
| Pull Request requise | ✅ Oui |
| Reviews requises | ✅ 1 minimum |
| Checks CI requis | ✅ Oui |
| Force push | ❌ Interdit |
| Suppression | ❌ Interdite |
| Historique linéaire | ✅ Oui |
| Admins soumis aux règles | ✅ Oui |

### Branche `develop`

| Règle | Valeur |
|-------|--------|
| Push direct | ⚠️ Déconseillé |
| Pull Request requise | ✅ Recommandée |
| Reviews requises | ⚠️ 1 recommandée |
| Checks CI requis | ✅ Oui |

---

## 💡 Bonnes pratiques

### Commits

**Format conventionnel :**
```
<type>(<scope>): <description>

[corps optionnel]

[footer optionnel]
```

**Types :**
- `feat` : Nouvelle fonctionnalité
- `fix` : Correction de bug
- `docs` : Documentation
- `style` : Formatage (pas de changement de logique)
- `refactor` : Refactorisation
- `test` : Tests
- `chore` : Maintenance

**Exemples :**
```
feat(auth): add OAuth2 authentication
fix(api): resolve timeout issue on upload
docs(readme): update installation instructions
refactor(client): simplify error handling
test(auth): add unit tests for login
chore(deps): update dependencies
```

### Pull Requests

**Titre :**
- Utiliser le même format que les commits
- Court et descriptif

**Description :**
- Décrire les changements
- Lier les issues (`Fixes #123`)
- Ajouter des screenshots si UI
- Lister les tests effectués

**Checklist avant PR :**
- [ ] Code testé localement
- [ ] Tests unitaires ajoutés
- [ ] Documentation mise à jour
- [ ] Pas de conflits avec la base
- [ ] CI passe

### Reviews

**En tant que reviewer :**
- Être bienveillant et constructif
- Expliquer les suggestions
- Distinguer bloquant vs nice-to-have
- Approuver quand c'est prêt

**En tant qu'auteur :**
- Répondre à tous les commentaires
- Expliquer les choix techniques
- Ne pas prendre les critiques personnellement

---

## 🚀 Releases

### Processus de release

1. **Créer une branche release**
   ```bash
   git checkout develop
   git checkout -b release/v1.2.0
   ```

2. **Corrections finales** (bugs, docs uniquement)
   ```bash
   git commit -m "chore(release): bump version to 1.2.0"
   ```

3. **Merge vers main**
   ```bash
   git checkout main
   git merge --no-ff release/v1.2.0
   git tag -a v1.2.0 -m "Release v1.2.0"
   ```

4. **Merge vers develop**
   ```bash
   git checkout develop
   git merge --no-ff release/v1.2.0
   ```

5. **Push et release GitHub**
   ```bash
   git push origin main --tags
   git push origin develop
   ```

### Hotfix

1. **Créer depuis main**
   ```bash
   git checkout main
   git checkout -b hotfix/critical-bug
   ```

2. **Corriger**
   ```bash
   git commit -m "fix: critical security vulnerability"
   ```

3. **Merge vers main et tag**
   ```bash
   git checkout main
   git merge --no-ff hotfix/critical-bug
   git tag -a v1.2.1 -m "Hotfix v1.2.1"
   ```

4. **Merge vers develop**
   ```bash
   git checkout develop
   git merge --no-ff hotfix/critical-bug
   ```

---

## 📚 Ressources

- [Git Flow](https://nvie.com/posts/a-successful-git-branching-model/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [GitHub Flow](https://guides.github.com/introduction/flow/)
- [Semantic Versioning](https://semver.org/)

---

## ❓ Questions ?

Si vous avez des questions sur le workflow :
- Ouvrez une [Discussion](https://github.com/guigui45dela-star/ToAD/discussions)
- Contactez un mainteneur

---

**Merci de suivre ces conventions pour garder le projet organisé ! 🐸**
