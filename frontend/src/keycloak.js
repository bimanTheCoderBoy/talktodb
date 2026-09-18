import Keycloak from "keycloak-js";

const keycloakUrl =  window.__RUNTIME_ENV__?.VITE_KEYCLOAK_URL ||  import.meta.env.VITE_KEYCLOAK_URL || "https://localhost:8443";
const keycloakRealm = import.meta.env.VITE_KEYCLOAK_REALM || "aan";
const keycloakClientId = import.meta.env.VITE_KEYCLOAK_CLIENT_ID || "react-app";
console.log(keycloakUrl, keycloakRealm, keycloakClientId);

const keycloak = new Keycloak({
  url: keycloakUrl,
  realm: keycloakRealm,
  clientId: keycloakClientId,
});

export default keycloak;