import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { api, tokenStore } from "@/lib/api";
import type { TokenPair, Usuario } from "@/types";

interface AuthState {
  user: Usuario | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  /** Comprueba permiso recurso:accion contra los permisos del rol (soporta comodín *). */
  can: (recurso: string, accion: string) => boolean;
}

const AuthCtx = createContext<AuthState | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Usuario | null>(null);
  const [loading, setLoading] = useState(true);

  const loadMe = async () => {
    if (!tokenStore.access) {
      setLoading(false);
      return;
    }
    try {
      const { data } = await api.get<Usuario>("/auth/me");
      setUser(data);
    } catch {
      tokenStore.clear();
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadMe();
    const onUnauth = () => {
      tokenStore.clear();
      setUser(null);
    };
    window.addEventListener("rappi2:unauthorized", onUnauth);
    return () => window.removeEventListener("rappi2:unauthorized", onUnauth);
  }, []);

  const login = async (username: string, password: string) => {
    const body = new URLSearchParams();
    body.append("username", username);
    body.append("password", password);
    const { data } = await api.post<TokenPair>("/auth/login", body, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });
    tokenStore.set(data);
    const me = await api.get<Usuario>("/auth/me");
    setUser(me.data);
  };

  const logout = async () => {
    const refresh = tokenStore.refresh;
    try {
      if (refresh) await api.post("/auth/logout", { refresh_token: refresh });
    } catch {
      /* ignore */
    }
    tokenStore.clear();
    setUser(null);
  };

  const can = (recurso: string, accion: string): boolean => {
    const permisos = user?.rol?.permisos ?? [];
    return permisos.some(
      (p) => (p.recurso === "*" || p.recurso === recurso) && (p.accion === "*" || p.accion === accion),
    );
  };

  const value = useMemo<AuthState>(() => ({ user, loading, login, logout, can }), [user, loading]);

  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthCtx);
  if (!ctx) throw new Error("useAuth debe usarse dentro de <AuthProvider>");
  return ctx;
}
