#!/bin/sh
KEYCLOAK_URL="${VITE_KEYCLOAK_URL:-"https://localhost:8443"}"
cat <<EOF > /usr/share/nginx/html/env-config.js
window.__RUNTIME_ENV__ = {
  VITE_KEYCLOAK_URL: "${KEYCLOAK_URL}"
};
EOF
echo "Injected Keycloak URL: ${KEYCLOAK_URL}"
exec "$@"
