import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { api } from "@/lib/api";
import keycloak, { initKeycloak } from "@/auth/keycloak";
import { tienePermiso } from "@/lib/permisos";
import type { Usuario } from "@/types";

interface AuthState {
  user: Usuario | null;
  loading: boolean;
  /** Redirige a Keycloak para iniciar sesión (OIDC Authorization Code + PKCE). */
  login: () => void;
  /** Cierra la sesión en Keycloak y vuelve a /login. */
  logout: () => void;
  /** Comprueba permiso recurso:accion contra los permisos del rol (soporta comodín *). */
  can: (recurso: string, accion: string) => boolean;
}

const AuthCtx = createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Usuario | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;

    initKeycloak()
      .then(async (authenticated) => {
        if (authenticated) {
          try {
            const { data } = await api.get<Usuario>("/auth/me");
            if (mounted) setUser(data);
          } catch {
            if (mounted) setUser(null);
          }
        }
        if (mounted) setLoading(false);
      })
      .catch(() => {
        if (mounted) setLoading(false);
      });

    // 401 desde el backend (token inválido/expirado sin refresh posible) -> limpiar.
    const onUnauth = () => setUser(null);
    window.addEventListener("rappi2:unauthorized", onUnauth);
    return () => {
      mounted = false;
      window.removeEventListener("rappi2:unauthorized", onUnauth);
    };
  }, []);

  const login = () => {
    void keycloak.login({ redirectUri: window.location.origin + "/" });
  };

  const logout = () => {
    setUser(null);
    void keycloak.logout({ redirectUri: window.location.origin + "/login" });
  };

  const can = (recurso: string, accion: string): boolean =>
    tienePermiso(user?.rol?.permisos, recurso, accion);

  const value = useMemo<AuthState>(
    () => ({ user, loading, login, logout, can }),
    [user, loading],
  );

  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthCtx);
  if (!ctx) throw new Error("useAuth debe usarse dentro de <AuthProvider>");
  return ctx;
}
