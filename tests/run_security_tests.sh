#!/bin/bash
# ============================================================================
# Script de test de sécurité pour ToAD
# ============================================================================
# 
# Ce script exécute les tests de sécurité pour valider les mesures implémentées.
# 
# Usage : ./tests/run_security_tests.sh
# 
# ============================================================================

set -e

# Couleurs pour l'affichage
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Variables
BASE_URL="http://localhost:9100"
TEST_TOKEN="test-token-for-security-tests-1234567890abcdef"
TESTS_PASSED=0
TESTS_FAILED=0

# Fonctions utilitaires
print_header() {
    echo -e "\n${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}\n"
}

print_test() {
    echo -n "  Testing: $1... "
}

print_success() {
    echo -e "${GREEN}✓ PASS${NC}"
    ((TESTS_PASSED++))
}

print_fail() {
    echo -e "${RED}✗ FAIL${NC}"
    ((TESTS_FAILED++))
}

print_info() {
    echo -e "${YELLOW}ℹ INFO${NC}: $1"
}

# ============================================================================
# Vérifications préliminaires
# ============================================================================

print_header "Vérifications préliminaires"

print_test "Vérification que ToAD est accessible"
if curl -s -f "$BASE_URL/api/health" > /dev/null 2>&1; then
    print_success
else
    print_fail
    echo -e "${RED}Erreur: ToAD n'est pas accessible sur $BASE_URL${NC}"
    echo -e "${YELLOW}Assurez-vous que ToAD est démarré : docker compose up -d${NC}"
    exit 1
fi

print_test "Vérification du endpoint /api/health"
HEALTH_RESPONSE=$(curl -s "$BASE_URL/api/health")
if echo "$HEALTH_RESPONSE" | grep -q '"status":"ok"'; then
    print_success
else
    print_fail
    echo -e "${RED}Erreur: Le endpoint /api/health ne retourne pas le statut attendu${NC}"
    exit 1
fi

# ============================================================================
# Tests d'authentification
# ============================================================================

print_header "Tests d'authentification"

print_test "Accès sans token (devrait être bloqué)"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/audits")
if [ "$HTTP_CODE" = "401" ]; then
    print_success
else
    print_fail
    echo -e "${RED}Code HTTP attendu: 401, obtenu: $HTTP_CODE${NC}"
fi

print_test "Accès avec token invalide (devrait être bloqué)"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer invalid-token" "$BASE_URL/api/audits")
if [ "$HTTP_CODE" = "401" ]; then
    print_success
else
    print_fail
    echo -e "${RED}Code HTTP attendu: 401, obtenu: $HTTP_CODE${NC}"
fi

print_test "Accès au endpoint /api/health sans token (devrait être autorisé)"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/health")
if [ "$HTTP_CODE" = "200" ]; then
    print_success
else
    print_fail
    echo -e "${RED}Code HTTP attendu: 200, obtenu: $HTTP_CODE${NC}"
fi

# ============================================================================
# Tests des headers de sécurité
# ============================================================================

print_header "Tests des headers de sécurité"

print_test "Header X-Content-Type-Options"
HEADERS=$(curl -sI "$BASE_URL/api/health")
if echo "$HEADERS" | grep -q "X-Content-Type-Options: nosniff"; then
    print_success
else
    print_fail
fi

print_test "Header X-Frame-Options"
if echo "$HEADERS" | grep -q "X-Frame-Options: DENY"; then
    print_success
else
    print_fail
fi

print_test "Header X-XSS-Protection"
if echo "$HEADERS" | grep -q "X-XSS-Protection"; then
    print_success
else
    print_fail
fi

print_test "Header Referrer-Policy"
if echo "$HEADERS" | grep -q "Referrer-Policy"; then
    print_success
else
    print_fail
fi

print_test "Header Content-Security-Policy"
if echo "$HEADERS" | grep -q "Content-Security-Policy"; then
    print_success
else
    print_fail
fi

# ============================================================================
# Tests de validation des entrées
# ============================================================================

print_header "Tests de validation des entrées"

print_test "Rejet des slugs invalides (path traversal)"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/clients/../../../etc/passwd")
if [ "$HTTP_CODE" = "400" ] || [ "$HTTP_CODE" = "404" ]; then
    print_success
else
    print_fail
    echo -e "${RED}Code HTTP attendu: 400 ou 404, obtenu: $HTTP_CODE${NC}"
fi

print_test "Rejet des slugs trop longs"
LONG_SLUG=$(python3 -c "print('a' * 100)")
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/clients/$LONG_SLUG")
if [ "$HTTP_CODE" = "400" ] || [ "$HTTP_CODE" = "404" ]; then
    print_success
else
    print_fail
    echo -e "${RED}Code HTTP attendu: 400 ou 404, obtenu: $HTTP_CODE${NC}"
fi

# ============================================================================
# Tests de rate limiting
# ============================================================================

print_header "Tests de rate limiting"

print_info "Envoi de 125 requêtes rapides pour tester le rate limiting"

RATE_LIMITED=false
for i in {1..125}; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/health")
    if [ "$HTTP_CODE" = "429" ]; then
        RATE_LIMITED=true
        print_test "Rate limiting activé après $i requêtes"
        print_success
        break
    fi
done

if [ "$RATE_LIMITED" = false ]; then
    print_test "Rate limiting non activé (peut être normal si configuré différemment)"
    print_info "Le rate limiting peut être désactivé ou configuré avec une limite plus haute"
fi

# ============================================================================
# Tests des endpoints principaux
# ============================================================================

print_header "Tests des endpoints principaux"

print_test "Endpoint /setup accessible"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/setup")
if [ "$HTTP_CODE" = "200" ]; then
    print_success
else
    print_fail
    echo -e "${RED}Code HTTP attendu: 200, obtenu: $HTTP_CODE${NC}"
fi

print_test "Endpoint / (index) accessible"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/")
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "307" ]; then
    print_success
else
    print_fail
    echo -e "${RED}Code HTTP attendu: 200 ou 307, obtenu: $HTTP_CODE${NC}"
fi

# ============================================================================
# Résumé
# ============================================================================

print_header "Résumé des tests"

TOTAL=$((TESTS_PASSED + TESTS_FAILED))

echo -e "  Tests effectués : ${BLUE}$TOTAL${NC}"
echo -e "  Tests réussis   : ${GREEN}$TESTS_PASSED${NC}"
echo -e "  Tests échoués   : ${RED}$TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ Tous les tests de sécurité sont passés !${NC}"
    echo -e "${GREEN}✓ ToAD est correctement configuré pour la production.${NC}"
    exit 0
else
    echo -e "${RED}✗ Certains tests ont échoué.${NC}"
    echo -e "${YELLOW}ℹ Veuillez vérifier la configuration de sécurité.${NC}"
    echo -e "${YELLOW}ℹ Consultez docs/security-configuration.md pour plus d'informations.${NC}"
    exit 1
fi
