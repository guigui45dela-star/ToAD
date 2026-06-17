# Politique de Sécurité

## Signaler une Vulnérabilité

Si vous découvrez une vulnérabilité de sécurité dans ToAD, merci de la signaler de manière responsable.

### Comment signaler

**Ne créez PAS une issue GitHub publique pour une vulnérabilité de sécurité.**

Envoyez plutôt un email à : [VOTRE_EMAIL@example.com]

Ou utilisez le formulaire de signalement privé de GitHub : https://github.com/guigui45dela-star/ToAD/security/advisories/new

### Informations à inclure

- Description de la vulnérabilité
- Étapes pour reproduire le problème
- Impact potentiel
- Toute suggestion de correction (optionnel)

### Ce que vous pouvez attendre

- Accusé de réception sous 48 heures
- Évaluation de la vulnérabilité sous 7 jours
- Plan de correction avec timeline
- Notification lorsque la correction est déployée

### Divulgation responsable

Nous suivons le processus de divulgation responsable :

1. **Signalement** : Vous signalez la vulnérabilité en privé
2. **Confirmation** : Nous confirmons la réception et évaluons
3. **Correction** : Nous développons et testons un correctif
4. **Divulgation** : Nous publions un avis de sécurité après déploiement
5. **Remerciements** : Nous vous créditons (si vous le souhaitez)

## Bonnes Pratiques de Sécurité

### Pour les utilisateurs

1. **Changez les mots de passe par défaut** lors de l'installation
2. **Utilisez HTTPS** avec un certificat SSL valide
3. **Activez l'authentification** (Basic Auth ou autre)
4. **Restreignez l'accès réseau** via firewall
5. **Mettez à jour régulièrement** vers la dernière version
6. **Sauvegardez vos données** régulièrement

### Pour les contributeurs

1. **Ne commitez jamais de credentials** dans le code
2. **Utilisez des variables d'environnement** pour les secrets
3. **Validez toutes les entrées** utilisateur
4. **Échappez le HTML** pour prévenir les XSS
5. **Utilisez des requêtes paramétrées** pour prévenir les injections SQL
6. **Testez la sécurité** avant de soumettre du code

## Versions Supportées

| Version | Supportée |
|---------|-----------|
| 1.0.x   | ✅ Oui    |
| < 1.0   | ❌ Non    |

## Historique des Sécurité

### Version 1.0.0 (2026-06-17)

- ✅ Aucun credential en dur
- ✅ Variables d'environnement pour tous les secrets
- ✅ Protection path traversal
- ✅ Validation des entrées
- ✅ Limites de taille sur uploads
- ✅ Confirmations avant actions destructives

## Ressources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)
- [GitHub Security Lab](https://securitylab.github.com/)

## Contact

Pour toute question concernant la sécurité :
- Email : [VOTRE_EMAIL@example.com]
- GitHub Security Advisory : https://github.com/guigui45dela-star/ToAD/security

---

Merci de nous aider à garder ToAD sécurisé ! 🔒
