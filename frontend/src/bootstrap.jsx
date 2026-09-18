/**
 * Bootstrap entry: when the app is opened over HTTP from a non-localhost URL
 * (e.g. http://d48d-ast-vm10.emea.teo.earth/ from another VM), the browser
 * treats it as an insecure context and crypto.subtle is unavailable.
 * We load the Web Crypto polyfill first (bundled, no CDN), then the app,
 * so Keycloak init works. Localhost and HTTPS are unaffected.
 */
(async function () {
  if (
    typeof window !== "undefined" &&
    !window.isSecureContext &&
    (!window.crypto || !window.crypto.subtle)
  ) {
    try {
      const mod = await import("webcrypto-liner-shim");
      if (!window.crypto?.subtle && mod?.default) {
        const C = mod.default;
        window.crypto = window.crypto || {};
        if (C.subtle) {
          window.crypto.subtle = C.subtle;
        } else if (typeof C === "function") {
          const instance = new C();
          if (instance?.subtle) window.crypto.subtle = instance.subtle;
        }
      }
    } catch (e) {
      console.warn("Web Crypto polyfill failed to load", e);
    }
  }
  await import("./main.jsx");
})();
