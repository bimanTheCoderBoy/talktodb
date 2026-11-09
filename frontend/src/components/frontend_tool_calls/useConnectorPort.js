import { useCallback, useState } from "react";

const STORAGE_KEY = "talktodb_connector_port";

export const CONNECTOR_HOST = "http://localhost";
export const DEFAULT_CONNECTOR_PORT = 2026;

function normalizePort(value) {
  const n = typeof value === "number" ? value : parseInt(String(value ?? "").trim(), 10);
  if (!Number.isFinite(n) || n < 1 || n > 65535) {
    return DEFAULT_CONNECTOR_PORT;
  }
  return n;
}

function readPortFromStorage() {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored != null && String(stored).trim() !== "") {
      return normalizePort(stored);
    }
  } catch {
    /* ignore */
  }
  return DEFAULT_CONNECTOR_PORT;
}

/** For non-React callers (e.g. run_db_query); reads latest from localStorage each time. */
export function getConnectorPort() {
  return readPortFromStorage();
}

export function getConnectorBaseUrl() {
  return `${CONNECTOR_HOST}:${getConnectorPort()}`;
}

export function setConnectorPort(next) {
  const saved = normalizePort(next);
  try {
    window.localStorage.setItem(STORAGE_KEY, String(saved));
  } catch {
    /* ignore */
  }
  return saved;
}

export function useConnectorPort() {
  const [port, setPortState] = useState(() => readPortFromStorage());

  const setPort = useCallback((next) => {
    const saved = setConnectorPort(next);
    setPortState(saved);
    return saved;
  }, []);

  return {
    port,
    setPort,
    baseUrl: `${CONNECTOR_HOST}:${port}`,
    defaultPort: DEFAULT_CONNECTOR_PORT,
  };
}
