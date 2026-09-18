#!/bin/bash
# ============================================================================
# TLS Certificate Generator for AANA Platform
# Generates self-signed certificates for Keycloak and Nginx HTTPS
#
# Usage:
#   ./generate-certs.sh                    # Uses defaults (localhost)
#   ./generate-certs.sh myserver.com       # Uses custom hostname
#   ./generate-certs.sh myserver.com 730   # Custom hostname + 730 days validity
#
# Output:
#   setup/certs/tls.crt   — Certificate (shared by Keycloak + Nginx)
#   setup/certs/tls.key   — Private key
# ============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERT_DIR="${SCRIPT_DIR}"
HOSTNAME="${1:-localhost}"
DAYS="${2:-365}"

echo "============================================"
echo "  AANA TLS Certificate Generator"
echo "============================================"
echo "  Hostname : ${HOSTNAME}"
echo "  Validity : ${DAYS} days"
echo "  Output   : ${CERT_DIR}/"
echo "============================================"

# Ensure certs directory exists
mkdir -p "${CERT_DIR}"

# Generate self-signed certificate with SAN (Subject Alternative Name)
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "mingw"* ]] && [ -z "$OPENSSL_CONF" ]; then
  export OPENSSL_CONF="/mingw64/etc/ssl/openssl.cnf"
fi
# SAN is required by modern browsers and Keycloak
openssl req -x509 -nodes -newkey rsa:2048 \
  -keyout "${CERT_DIR}/tls.key" \
  -out "${CERT_DIR}/tls.crt" \
  -days "${DAYS}" \
  -subj "/CN=${HOSTNAME}/O=TEOCO/OU=AANA" \
  -addext "subjectAltName=DNS:${HOSTNAME},DNS:localhost,DNS:keycloak-server,IP:127.0.0.1"

# Set permissions — both files must be readable by the non-root user the
# Keycloak container runs as (uid 1000). Tightening tls.key to 600 owned by
# the deploy user locks the container out and Keycloak crash-loops with
# `ERROR: /opt/keycloak/conf/tls.key`. Self-signed dev cert, so 644 is fine;
# for production use a CA-signed cert with proper ownership + 640.
chmod 644 "${CERT_DIR}/tls.crt"
chmod 644 "${CERT_DIR}/tls.key"

echo ""
echo "Certificates generated successfully:"
echo "  Certificate : ${CERT_DIR}/tls.crt"
echo "  Private Key : ${CERT_DIR}/tls.key"
echo ""
echo "Certificate details:"
openssl x509 -in "${CERT_DIR}/tls.crt" -noout -subject -dates -ext subjectAltName 2>/dev/null || \
  openssl x509 -in "${CERT_DIR}/tls.crt" -noout -subject -dates
echo ""
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
echo "Next steps:"
echo "  1. docker compose (repo root) mounts ${CERT_DIR} -> frontend /etc/nginx/certs & keycloak — no copy needed."
echo "  2. Restart frontend:  cd ${REPO_ROOT} && docker compose up -d frontend"
echo "  3. (Optional) auth server Keycloak:  cd ${REPO_ROOT}/auth_server && docker compose up -d"
echo ""
echo "For server deployment, replace these with real CA-signed certificates."
