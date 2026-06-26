import axios, { AxiosError } from "axios";
import { getToken } from "@/auth/keycloak";

const API_URL = import.meta.env.VITE_API_URL || "/api";

// indexes: null serializa los arrays como claves repetidas (orden_ids=1&orden_ids=2),
// que es lo que esperan los Query params tipo list[int] de FastAPI (sin esto, axios
// usa orden_ids[]=… y el backend no los enlaza → p. ej. "Sugerir conductor" fallaba).
export const api = axios.create({ baseURL: API_URL, paramsSerializer: { indexes: null } });

// El Bearer lo provee Keycloak: getToken() refresca el access token si está por expirar.
api.interceptors.request.use(async (config) => {
  const token = await getToken();
  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (error: AxiosError) => {
    // Token inválido/expirado sin refresh posible: forzar el flujo de login.
    if (error.response?.status === 401) {
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
