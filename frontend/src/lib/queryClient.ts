import { QueryCache, QueryClient } from "@tanstack/react-query";
import { AxiosError } from "axios";
import toast from "react-hot-toast";

/** Mensaje legible para fallos de red/servidor en QUERIES (lecturas).
 *  Las mutaciones no pasan por aquí: cada llamada a mutate() ya muestra su propio
 *  toast contextual con apiError(). */
function mensajeDeError(err: unknown): string | null {
  const e = err as AxiosError;
  if (e?.code === "ERR_NETWORK") return "Sin conexión con el servidor. Revisa tu red e inténtalo de nuevo.";
  const status = e?.response?.status;
  if (status === 401) return null; // lo maneja el interceptor de api.ts (re-login)
  if (status && status >= 500) return "El servidor tuvo un problema al cargar los datos. Vuelve a intentarlo.";
  if (status === 403) return "No tienes permiso para ver parte de esta información.";
  return null; // el resto (4xx puntuales) lo maneja cada pantalla si le aplica
}

export const queryClient = new QueryClient({
  // Aviso global cuando una lectura falla tras agotar el retry (antes cada pantalla
  // fallaba en silencio y el usuario veía una tabla vacía sin explicación).
  queryCache: new QueryCache({
    onError: (err) => {
      const msg = mensajeDeError(err);
      // id fijo: si fallan varias queries a la vez (p. ej. red caída), un solo toast.
      if (msg) toast.error(msg, { id: "query-error" });
    },
  }),
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 15_000,
    },
  },
});
