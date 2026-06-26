import Keycloak from "keycloak-js";

// Instancia singleton de Keycloak (OIDC). La autenticación la maneja por completo
// Keycloak (Authorization Code + PKCE): el backend solo valida el access token.
const keycloak = new Keycloak({
  url: import.meta.env.VITE_KEYCLOAK_URL || "http://localhost:8080",
  realm: import.meta.env.VITE_KEYCLOAK_REALM || "rappi2",
  clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID || "rappi2-frontend",
});

let initPromise: Promise<boolean> | null = null;

/** Inicializa Keycloak una sola vez. Devuelve si la sesión está autenticada.
 *  `check-sso` restaura la sesión silenciosamente (vía /silent-check-sso.html) sin
 *  forzar un redirect cuando el usuario aún no inició sesión. */
export function initKeycloak(): Promise<boolean> {
  if (!initPromise) {
    initPromise = keycloak.init({
      onLoad: "check-sso",
      silentCheckSsoRedirectUri: `${window.location.origin}/silent-check-sso.html`,
      pkceMethod: "S256",
      checkLoginIframe: false,
    });
  }
  return initPromise;
}

/** Access token vigente, refrescándolo si está por expirar (<30s). null si no hay sesión. */
export async function getToken(): Promise<string | null> {
  try {
    await keycloak.updateToken(30);
    return keycloak.token ?? null;
  } catch {
    return null;
  }
}

export default keycloak;
