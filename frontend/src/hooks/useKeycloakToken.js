import { useState, useEffect } from "react";
import keycloak from "../keycloak";

/**
 * Bridges keycloak-js token lifecycle events with React state.
 * Returns the current access token and triggers re-renders when it refreshes.
 */
export function useKeycloakToken() {
  const [token, setToken] = useState(keycloak.token);

  useEffect(() => {
    const handleRefreshSuccess = () => {
      setToken(keycloak.token);
    };

    const handleTokenExpired = () => {
      keycloak.updateToken(30).catch(() => {
        console.error("Failed to refresh token on expiry");
        keycloak.logout();
      });
    };

    keycloak.onAuthRefreshSuccess = handleRefreshSuccess;
    keycloak.onTokenExpired = handleTokenExpired;

    return () => {
      keycloak.onAuthRefreshSuccess = undefined;
      keycloak.onTokenExpired = undefined;
    };
  }, []);

  useEffect(() => {
    if (keycloak.token && keycloak.token !== token) {
      setToken(keycloak.token);
    }
  });

  return token;
}
