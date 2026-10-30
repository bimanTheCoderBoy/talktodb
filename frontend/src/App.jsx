import React, { useState, useEffect, Suspense, lazy, useRef } from "react";
import { ToastContainer } from "react-toastify";
import LoadingPage from "./components/LoadingPage";
import keycloak from "./keycloak";

const Wrapper = lazy(() => import("./components/Wrapper"));

function App() {
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthLoading, setIsAuthLoading] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [authErrorMessage, setAuthErrorMessage] = useState(null);
  const initialized = useRef(false);
  const interval = useRef(null);

  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    setIsAuthLoading(true);

    if (keycloak.authenticated) {
      setIsAuthenticated(true);
      setIsLoading(false);
      setIsAuthLoading(false);
      return;
    }

    keycloak
      .init({
        onLoad: "check-sso",
        checkLoginIframe: false,
        silentCheckSsoRedirectUri: window.location.origin + "/silent-check-sso.html",
      })
      .then((authenticated) => {
        if (!authenticated) {
          keycloak.login();
          setIsAuthenticated(false);
          initialized.current = false;
          return;
        }
        localStorage.setItem("keycloak-token", keycloak.token);
        setIsAuthenticated(true);
        interval.current = setInterval(() => {
          keycloak
            .updateToken(30)
            .then((refreshed) => {
              if (refreshed) localStorage.setItem("keycloak-token", keycloak.token);
            })
            .catch(() => keycloak.logout());
        }, 10000);
      })
      .catch((error) => {
        setAuthErrorMessage(error.message);
      })
      .finally(() => setIsAuthLoading(false));

    return () => {
      initialized.current = false;
      if (interval.current) clearInterval(interval.current);
    };
  }, []);

  useEffect(() => {
    const handleLoad = () => setTimeout(() => setIsLoading(false), 500);
    if (document.readyState === "complete") handleLoad();
    else window.addEventListener("load", handleLoad);
    return () => window.removeEventListener("load", handleLoad);
  }, []);

  return (
    <div className="App h-full w-full">
      {isLoading || isAuthLoading ? (
        <LoadingPage />
      ) : isAuthenticated ? (
        <Suspense fallback={<LoadingPage />}>
          <Wrapper />
        </Suspense>
      ) : (
        <div className="flex flex-col items-center justify-center h-screen bg-background">
          <div className="text-2xl font-bold text-foreground">
            {authErrorMessage ? `Sign-in failed: ${authErrorMessage}` : "Please sign in"}
          </div>
          <button
            type="button"
            className="mt-4 px-4 py-2 bg-blue-500 text-white rounded-md cursor-pointer"
            onClick={() => keycloak.login()}
          >
            Login
          </button>
        </div>
      )}
      <ToastContainer
        theme="dark"
        className="app-toast-container"
        toastClassName="app-toast"
        bodyClassName="app-toast-body"
        progressClassName="app-toast-progress"
      />
    </div>
  );
}

export default App;
