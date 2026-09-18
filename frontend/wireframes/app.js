// raNora wireframes — hash router + UI plumbing
(function () {
  "use strict";

  const ROUTES = {
    "":                        { title: "Dashboard",          screen: "home" },
    "home":                    { title: "Dashboard",          screen: "home" },
    "agents":                  { title: "Agents · Library",   screen: "agents" },
    "agent/asset-db":          { title: "Asset DB Agent",     screen: "agent/asset-db" },
    "agent/coverage":          { title: "Coverage Agent",     screen: "agent/coverage" },
    "agent/cm":                { title: "CM Agent · CoC",     screen: "agent/cm" },
    "agent/ztp":               { title: "ZTP Agent",          screen: "agent/ztp" },
    "settings/models":         { title: "Models · Routing",   screen: "settings/models" },
    "settings/flags":          { title: "Feature flags",      screen: "settings/flags" },
    "settings/integrations":   { title: "Integrations",       screen: "settings/integrations" },
    "settings/audit":          { title: "Audit log",          screen: "settings/audit" },
    "settings/tools":          { title: "Tools · Permissions",screen: "settings/tools" },
    "settings/profile":        { title: "Profile",            screen: "settings/profile" },
    "admin/projects":          { title: "Projects",           screen: "admin/projects" },
    "admin/users":             { title: "Users · Roles",      screen: "admin/users" },
    "admin/system":            { title: "System health",      screen: "admin/system" },
    "threads":                 { title: "Threads",            screen: "threads" },
    "sessions":                { title: "Sessions",           screen: "sessions" },
    "reports":                 { title: "Reports",            screen: "reports" },
  };

  const host       = document.getElementById("screen-host");
  const crumbHere  = document.getElementById("crumbHere");
  const railLinks  = document.querySelectorAll("[data-route-link]");
  const appEl      = document.querySelector(".app");

  // ============== Role (User vs Power user) ==============
  const ROLE_KEY = "ranora.wireframe.role";
  function getRole() {
    return localStorage.getItem(ROLE_KEY) || "user";
  }
  function setRole(role) {
    localStorage.setItem(ROLE_KEY, role);
    appEl.setAttribute("data-role", role);
    document.querySelectorAll(".role-switch__opt").forEach((b) => {
      b.classList.toggle("is-on", b.getAttribute("data-role") === role);
    });
    // re-render current screen so user-mode / power-mode markup swaps in
    render(currentRoute());
  }
  window.__getRole = getRole;
  // initial paint
  appEl.setAttribute("data-role", getRole());
  document.querySelectorAll(".role-switch__opt").forEach((b) => {
    b.classList.toggle("is-on", b.getAttribute("data-role") === getRole());
    b.addEventListener("click", () => setRole(b.getAttribute("data-role")));
  });

  function currentRoute() {
    const raw = (location.hash || "").replace(/^#/, "");
    return ROUTES[raw] ? raw : (ROUTES[raw.split("/")[0]] ? raw.split("/")[0] : "home");
  }

  function render(routeKey) {
    const route = ROUTES[routeKey] || ROUTES.home;
    const screenKey = route.screen;
    const builder = window.SCREENS[screenKey];
    host.innerHTML = builder ? builder() : `<div class="screen is-active"><h2 class="h2">Not built yet · <em>${routeKey}</em></h2></div>`;
    if (crumbHere) crumbHere.textContent = route.title;
    document.title = `raNora · ${route.title} — Wireframes`;
    railLinks.forEach((a) => {
      const k = a.getAttribute("data-route-link");
      a.classList.toggle("is-active", k === routeKey || routeKey.startsWith(k + "/"));
    });
    host.scrollTop = 0;
    document.querySelector(".canvas").scrollTop = 0;
  }

  function onHashChange() {
    render(currentRoute());
  }

  // ============== Command palette ==============
  const palette = document.getElementById("palette");
  window.openPalette = function () {
    palette.hidden = false;
    setTimeout(() => palette.querySelector(".palette__input")?.focus(), 0);
  };
  function closePalette() { palette.hidden = true; }
  palette.addEventListener("click", (e) => {
    if (e.target.matches("[data-close-palette]")) closePalette();
    const link = e.target.closest("a[href^='#']");
    if (link) closePalette();
  });
  document.addEventListener("keydown", (e) => {
    const meta = e.metaKey || e.ctrlKey;
    if (meta && e.key.toLowerCase() === "k") { e.preventDefault(); window.openPalette(); }
    if (e.key === "Escape") closePalette();
  });

  // ============== Tri-state toggles + simple toggles ==============
  document.addEventListener("click", (e) => {
    const tri = e.target.closest(".tri__opt");
    if (tri) {
      const group = tri.parentElement;
      group.querySelectorAll(".tri__opt").forEach((o) => o.classList.remove("is-on"));
      tri.classList.add("is-on");
      return;
    }
    const tog = e.target.closest(".toggle");
    if (tog) tog.classList.toggle("is-on");
  });

  // ============== Boot ==============
  window.addEventListener("hashchange", onHashChange);
  document.addEventListener("DOMContentLoaded", onHashChange);
  // Run once immediately too (in case DOMContentLoaded already fired):
  if (document.readyState !== "loading") onHashChange();
})();
