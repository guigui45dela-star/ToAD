# Guide de Contribution

Merci de votre intérêt pour contribuer à ToAD ! Ce document fournit les lignes directrices pour contribuer au projet.

## 🎯 Comment contribuer

### Signaler des bugs

1. Vérifiez que le bug n'a pas déjà été signalé dans les [Issues](https://github.com/your-username/toad/issues)
2. Créez une nouvelle issue en utilisant le template "Bug Report"
3. Fournissez :
   - Description claire du problème
   - Étapes pour reproduire
   - Comportement attendu vs observé
   - Environnement (OS, Docker version, etc.)
   - Logs pertinents

### Suggérer des fonctionnalités

1. Vérifiez que la fonctionnalité n'existe pas déjà
2. Créez une issue avec le template "Feature Request"
3. Décrivez :
   - Le cas d'usage
   - La solution proposée
   - Les alternatives considérées

### Soumettre du code

1. **Fork** le repository
2. **Clone** votre fork
   ```bash
   git clone https://github.com/your-username/toad.git
   cd toad
   ```
3. **Créez une branche** pour votre fonctionnalité
   ```bash
   git checkout -b feature/ma-fonctionnalite
   ```
4. **Développez** vos changements
5. **Testez** thoroughly
6. **Commit** avec des messages clairs
   ```bash
   git commit -m "feat: ajoute support pour XYZ"
   ```
7. **Push** vers votre fork
   ```bash
   git push origin feature/ma-fonctionnalite
   ```
8. **Ouvrez une Pull Request** vers la branche `main`

## 📝 Standards de code

### Python (Backend)

- **Style** : PEP 8
- **Formatage** : Utilisez `black` ou `ruff`
- **Imports** : Triés avec `isort`
- **Docstrings** : Google style pour les fonctions publiques
- **Type hints** : Obligatoires pour les fonctions publiques

```python
def example_function(param1: str, param2: int) -> dict:
    """
    Description courte de la fonction.

    Args:
        param1: Description du paramètre
        param2: Description du paramètre

    Returns:
        Description de la valeur de retour

    Raises:
        ValueError: Quand le paramètre est invalide
    """
    pass
```

### JavaScript/HTML (Frontend)

- **Style** : ES6+
- **Indentation** : 2 espaces
- **Noms** : camelCase pour variables/fonctions
- **Commentaires** : En français ou anglais, cohérent dans un fichier

```javascript
function exampleFunction(param1, param2) {
  // Description courte
  const result = param1 + param2;
  return result;
}
```

### Commits

Utilisez le format [Conventional Commits](https://www.conventionalcommits.org/) :

```
feat: ajoute support pour les tags
fix: corrige bug de validation slug
docs: met à jour README avec screenshots
refactor: optimise latest_file_date()
test: ajoute tests pour safe_path()
chore: met à jour dépendances
```

Types :
- `feat` : Nouvelle fonctionnalité
- `fix` : Correction de bug
- `docs` : Documentation
- `style` : Formatage (pas de changement de logique)
- `refactor` : Refactorisation
- `test` : Tests
- `chore` : Maintenance

## 🔍 Process de Review

1. **CI/CD** : Les tests doivent passer
2. **Review** : Au moins 1 approbation requise
3. **Conflits** : Résolvez les conflits avant merge
4. **Squash** : Les commits sont squashés au merge

## 🧪 Tests

### Backend

```bash
# Lancer les tests
pytest tests/

# Avec couverture
pytest --cov=web tests/
```

### Frontend

```bash
# Tests à implémenter
# Utiliser Jest ou Vitest
```

## 📚 Documentation

- Mettez à jour la documentation si vous changez des fonctionnalités
- Ajoutez des docstrings pour les nouvelles fonctions
- Mettez à jour le README si nécessaire

## 🚀 Workflow de release

1. **Version bump** : Mise à jour de la version dans `package.json` et `README.md`
2. **Changelog** : Mise à jour de `CHANGELOG.md`
3. **Tag** : Création d'un tag Git
   ```bash
   git tag v1.2.0
   git push origin v1.2.0
   ```
4. **Release GitHub** : Création d'une release avec les notes

## 💬 Communication

- **Issues** : Pour bugs et features
- **Discussions** : Pour questions générales
- **PR** : Pour soumettre du code

## 🎓 Ressources

- [Documentation FastAPI](https://fastapi.tiangolo.com/)
- [Documentation BloodHound CE](https://support.bloodhoundenterprise.io/)
- [Documentation AD-Miner](https://github.com/Mazars-Tech/AD_Miner)

## ❓ Questions ?

N'hésitez pas à ouvrir une [Discussion](https://github.com/your-username/toad/discussions) pour toute question.

---

Merci de contribuer à ToAD ! 🐸
