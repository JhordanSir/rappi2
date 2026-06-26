import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { getToken } from "@/auth/keycloak";

const API_URL = import.meta.env.VITE_API_URL || "/api";

/**
 * Abre una conexión SSE con el backend (`/realtime/stream`) y reacciona a los
 * eventos en tiempo real invalidando las queries de react-query afectadas, de
 * modo que la UI (campana de notificaciones, listas de órdenes, seguimiento) se
 * actualiza sola sin esperar al polling. El token viaja por query param porque
 * EventSource no permite cabeceras. Reconecta automáticamente ante errores.
 */
export function useRealtime(enabled = true) {
  const qc = useQueryClient();
  useEffect(() => {
    if (!enabled) return;
    let es: EventSource | null = null;
    let retry: ReturnType<typeof setTimeout> | null = null;
    let closed = false;

    const connect = async () => {
      const token = await getToken();
      if (closed || !token) return;
      es = new EventSource(`${API_URL}/realtime/stream?token=${encodeURIComponent(token)}`);

      es.onmessage = (ev) => {
        let data: any;
        try {
          data = JSON.parse(ev.data);
        } catch {
          return;
        }
        if (data?.tipo === "notificacion") {
          qc.invalidateQueries({ queryKey: ["notificaciones"] });
          if (data.titulo) toast(data.titulo, { icon: "🔔" });
        } else if (data?.tipo === "orden" || data?.tipo === "pago") {
          qc.invalidateQueries({ queryKey: ["ordenes"] });
          qc.invalidateQueries({ queryKey: ["mis-ordenes"] });
          qc.invalidateQueries({ queryKey: ["seguimiento"] });
          if (data.orden_id) qc.invalidateQueries({ queryKey: ["orden", data.orden_id] });
        }
      };

      es.onerror = () => {
        es?.close();
        es = null;
        if (!closed) retry = setTimeout(() => void connect(), 3000);
      };
    };

    void connect();
    return () => {
      closed = true;
      if (retry) clearTimeout(retry);
      es?.close();
    };
  }, [enabled, qc]);
}
