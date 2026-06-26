import axios, { AxiosError, AxiosRequestConfig } from "axios";
import type { TokenPair } from "@/types";

const API_URL = import.meta.env.VITE_API_URL || "/api";

const ACCESS_KEY = "rappi2_access";
const REFRESH_KEY = "rappi2_refresh";

export const tokenStore = {
  get access() {
    return localStorage.getItem(ACCESS_KEY);
  },
  get refresh() {
    return localStorage.getItem(REFRESH_KEY);
  },
  set(pair: TokenPair) {
    localStorage.setItem(ACCESS_KEY, pair.access_token);
    localStorage.setItem(REFRESH_KEY, pair.refresh_token);
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

// indexes: null serializa los arrays como claves repetidas (orden_ids=1&orden_ids=2),
// que es lo que esperan los Query params tipo list[int] de FastAPI (sin esto, axios
// usa orden_ids[]=… y el backend no los enlaza → p. ej. "Sugerir conductor" fallaba).
export const api = axios.create({ baseURL: API_URL, paramsSerializer: { indexes: null } });

api.interceptors.request.use((config) => {
  const token = tokenStore.access;
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Refresh con cola para evitar multiples refresh concurrentes.
let refreshing: Promise<string | null> | null = null;

async function doRefresh(): Promise<string | null> {
  const refresh = tokenStore.refresh;
  if (!refresh) return null;
  try {
    const { data } = await axios.post<TokenPair>(`${API_URL}/auth/refresh`, {
      refresh_token: refresh,
    });
    tokenStore.set(data);
    return data.access_token;
  } catch {
    tokenStore.clear();
    return null;
  }
}

api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const original = error.config as AxiosRequestConfig & { _retry?: boolean };
    const status = error.response?.status;
    const isAuthCall = original?.url?.includes("/auth/");

    if (status === 401 && original && !original._retry && !isAuthCall) {
      original._retry = true;
      if (!refreshing) refreshing = doRefresh();
      const newToken = await refreshing;
      refreshing = null;
      if (newToken) {
        original.headers = original.headers ?? {};
        (original.headers as Record<string, string>).Authorization = `Bearer ${newToken}`;
        return api(original);
      }
      // refresh fallido -> forzar logout
      window.dispatchEvent(new CustomEvent("rappi2:unauthorized"));
    }
    return Promise.reject(error);
  },
);

/** Extrae un mensaje de error legible desde una respuesta del backend FastAPI. */
export function apiError(err: unknown): string {
  const e = err as AxiosError<any>;
  const detail = e?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((d: any) => `${d.loc?.slice(-1)[0] ?? ""}: ${d.msg}`).join(" · ");
  }
  return e?.message || "Ocurrió un error inesperado";
}
