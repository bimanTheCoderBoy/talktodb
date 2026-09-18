import React, { useState, useEffect, Suspense, lazy, useRef } from "react";
import { ToastContainer } from 'react-toastify';
import { ProjectProvider } from "./context/ProjectContext";
import { Routes, Route } from "react-router-dom";
import LoadingPage from "./components/LoadingPage";
import keycloak from "./keycloak";
const PdfViewer = lazy(() => import("./pages/PdfViewer"));
const Wrapper = lazy(() => import("./components/Wrapper"));
const MapViewer2D = lazy(() => import("@/coverage_map_viewer/2d/MapViewer2D"));
const ACSSModule = lazy(() => import("./acss_module"));
const ACSSProvider = lazy(() =>
  import('./acss_module/context/ACSSContext').then((m) => ({ default: m.ACSSProvider }))
);
const AdminSetUpConfig = lazy(() => import("./pages/AdminSetUpConfig"));

function App() {
  const [isLoading, setIsLoading] = useState(true);
  const [isAuthLoading, setIsAuthLoading] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [authErrorMessage, setAuthErrorMessage] = useState(null);

  const initialized = useRef(false);
  const interval = useRef(null);
  //very imp keycloak init
  useEffect(() => {
    if (initialized.current) return;
    initialized.current = true;
    setIsAuthLoading(true);
    if (keycloak.authenticated) {
      setIsAuthenticated(true);
      setIsLoading(false);
      setIsAuthLoading(false);
    } else {
      setIsAuthLoading(true);
      keycloak
        .init({
          onLoad: "check-sso",
          checkLoginIframe: false,
          silentCheckSsoRedirectUri: window.location.origin + '/silent-check-sso.html',
          // pkceMethod: "S256",
        })
        .then((authenticated) => {
          if (!authenticated) {
            console.error("Not authenticated");
            keycloak.login();
            setIsAuthenticated(false);
            setIsAuthLoading(false);
            initialized.current = false;
            if (interval.current) {
              clearInterval(interval.current);
            }
            return;
          } else {
            localStorage.setItem("keycloak-token", keycloak.token);
            setIsAuthenticated(true);
          }

        interval.current = setInterval(() => {
            keycloak
              .updateToken(30)
              .then((refreshed) => {
                if (refreshed) {
                  localStorage.setItem("keycloak-token", keycloak.token);
                  console.log("Token refreshed");
                }
              })
              .catch(() => {
                console.error("Failed to refresh token");
                keycloak.logout();
              });
          }, 10000);
       

        })
        .catch((error) => {
          console.error("Keycloak init failed", error);
          setAuthErrorMessage(error.message);
         
        })
        .finally(() => {
          setIsAuthLoading(false);
        });
    }
    return () => {
      initialized.current = false;
      if (interval.current) {
        clearInterval(interval.current);
      }
    };

  },

    []);



  useEffect(() => {
    // Hide loading when window is fully loaded
    const handleLoad = () => {
      setTimeout(() => {
        setIsLoading(false);
        setIsAuthLoading(false);
      }, 500); // Small delay for smooth transition
    };

    if (document.readyState === 'complete') {
      handleLoad();
    } else {
      window.addEventListener('load', handleLoad);
    }

    return () => {

      window.removeEventListener('load', handleLoad);
    };
  }, []);

  const isAdmin = keycloak.tokenParsed?.realm_access?.roles.includes('CONFIG_MANAGEMENT');
  return (
    <div className="App h-full w-full">
      {(isLoading || isAuthLoading) ? <LoadingPage />
        : isAuthenticated ? <ProjectProvider>
          <Suspense fallback={<LoadingPage />}>
            <Routes>
              <Route path="/" element={<Wrapper />} />
              <Route path="/map/2d/*" element={<ACSSProvider><MapViewer2D /></ACSSProvider>} />
              <Route path="/asp/:project_name/:acss_session_id" element={<ACSSProvider><ACSSModule /></ACSSProvider>} />
              <Route path="/pdf/:file_name" element={<PdfViewer />} />
              {isAdmin && (
                <>
                  <Route path="/admin/set-up/config" element={<AdminSetUpConfig />} />
                </>
              )}
              {/* <Route path="/reports" element={<>reports will be here</>} /> */}
            </Routes>
          </Suspense>
        </ProjectProvider>
        // THEME: bg-gradient → bg-background, text-white → text-foreground (adapts error screen to theme)
        : <div className="flex flex-col items-center justify-center h-screen bg-background">
        <div className="text-2xl font-bold text-foreground">Keycloak init failed: {authErrorMessage}</div>
        <button className="mt-4 px-4 py-2 bg-blue-500 text-white rounded-md cursor-pointer" onClick={() => keycloak.login()}>Login</button>
      </div>
      }
      <ToastContainer
        theme="dark"
        className="teoco-toast-container"
        toastClassName="teoco-toast"
        bodyClassName="teoco-toast-body"
        progressClassName="teoco-toast-progress"
      />
    </div>
  );
}

export default App;
