import { useEffect, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type {
  Asignacion,
  Auditoria,
  Cliente,
  Conductor,
  EntregaEvidencia,
  Evidencia,
  Factura,
  Geocerca,
  GPSPing,
  Incidencia,
  Notificacion,
  Orden,
  OrdenSeguimiento,
  Pago,
  Rol,
  Ruta,
  Usuario,
  Vehiculo,
} from "@/types";

type Params = Record<string, any> | undefined;

function get<T>(url: string, params?: Params) {
  return api.get<T>(url, { params }).then((r) => r.data);
}

export type Page<T> = { items: T[]; total: number };

/**
 * Listado paginado server-side: el body es la página (array) y el total de
 * registros que matchean el filtro viaja en el header `X-Total-Count`.
 * Mantiene la página anterior visible mientras carga la siguiente.
 */
export function usePaginated<T>(key: string, url: string, params?: Params) {
  return useQuery({
    queryKey: [key, params],
    queryFn: async (): Promise<Page<T>> => {
      const r = await api.get<T[]>(url, { params });
      const total = Number(r.headers["x-total-count"] ?? r.data.length);
      return { items: r.data, total: Number.isNaN(total) ? r.data.length : total };
    },
    placeholderData: keepPreviousData,
  });
}

/** Devuelve `value` con un retraso, para no disparar una request por tecla. */
export function useDebouncedValue<T>(value: T, delay = 350): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(t);
  }, [value, delay]);
  return debounced;
}

// ---------------- Clientes ----------------
export const useClientes = (params?: Params, enabled = true) =>
  useQuery({ queryKey: ["clientes", params], queryFn: () => get<Cliente[]>("/clientes/", params), enabled });
export const useCliente = (id?: number) =>
  useQuery({ queryKey: ["cliente", id], queryFn: () => get<Cliente>(`/clientes/${id}`), enabled: !!id });

// ---------------- Ordenes ----------------
export const useOrdenes = (params?: Params) =>
  useQuery({ queryKey: ["ordenes", params], queryFn: () => get<Orden[]>("/ordenes/", params) });
export const useOrden = (id?: number) =>
  useQuery({ queryKey: ["orden", id], queryFn: () => get<Orden>(`/ordenes/${id}`), enabled: !!id });
export const useSeguimiento = (ordenId?: number, refetchMs?: number) =>
  useQuery({
    queryKey: ["seguimiento", ordenId],
    queryFn: () => get<OrdenSeguimiento>(`/tracking/orden/${ordenId}`),
    enabled: !!ordenId,
    refetchInterval: refetchMs,
  });

// ---------------- Conductores / Vehiculos ----------------
export const useConductores = (params?: Params) =>
  useQuery({ queryKey: ["conductores", params], queryFn: () => get<Conductor[]>("/conductores/", params) });
export const useVehiculos = (params?: Params) =>
  useQuery({ queryKey: ["vehiculos", params], queryFn: () => get<Vehiculo[]>("/vehiculos/", params) });

// ---------------- Asignaciones ----------------
export const useAsignaciones = (params?: Params) =>
  useQuery({ queryKey: ["asignaciones", params], queryFn: () => get<Asignacion[]>("/asignaciones/", params) });
/** Pruebas de entrega (fotos/firmas en GridFS) de una asignación — para auditoría del admin. */
export const usePruebasEntrega = (asignacionId?: number) =>
  useQuery({
    queryKey: ["pruebas-entrega", asignacionId],
    queryFn: () => get<EntregaEvidencia[]>(`/asignaciones/${asignacionId}/prueba-entrega`),
    enabled: !!asignacionId,
  });

// ---------------- Rutas ----------------
export const useRutas = (params?: Params) =>
  useQuery({ queryKey: ["rutas", params], queryFn: () => get<Ruta[]>("/rutas/", params) });

// ---------------- Incidencias ----------------
export const useIncidencias = (params?: Params) =>
  useQuery({ queryKey: ["incidencias", params], queryFn: () => get<Incidencia[]>("/incidencias/", params) });

// ---------------- Pagos / Facturas ----------------
export const usePagos = (params?: Params) =>
  useQuery({ queryKey: ["pagos", params], queryFn: () => get<Pago[]>("/pagos", params) });
export const useFacturas = (params?: Params) =>
  useQuery({ queryKey: ["facturas", params], queryFn: () => get<Factura[]>("/facturas", params) });

// ---------------- Usuarios / Roles ----------------
export const useUsuarios = (params?: Params) =>
  useQuery({ queryKey: ["usuarios", params], queryFn: () => get<Usuario[]>("/usuarios/", params) });
export const useRoles = () => useQuery({ queryKey: ["roles"], queryFn: () => get<Rol[]>("/roles/") });

// ---------------- Tracking ----------------
export const useUltimoPing = (asignacionId?: number, refetchMs?: number) =>
  useQuery({
    queryKey: ["ultimo-ping", asignacionId],
    queryFn: () => get<GPSPing>(`/tracking/asignacion/${asignacionId}/ultimo`),
    enabled: !!asignacionId,
    refetchInterval: refetchMs,
    retry: false,
  });
export const usePings = (asignacionId?: number, params?: Params) =>
  useQuery({
    queryKey: ["pings", asignacionId, params],
    queryFn: () => get<GPSPing[]>(`/tracking/asignacion/${asignacionId}`, params),
    enabled: !!asignacionId,
  });

// ---------------- Notificaciones ----------------
export const useNotificaciones = (params?: Params, refetchMs?: number) =>
  useQuery({
    queryKey: ["notificaciones", params],
    queryFn: () => get<Notificacion[]>("/notificaciones/mias", params),
    refetchInterval: refetchMs,
  });

// ---------------- Geocercas ----------------
export const useGeocercas = (params?: Params) =>
  useQuery({ queryKey: ["geocercas", params], queryFn: () => get<Geocerca[]>("/geocercas", params) });

// ---------------- Auditoría ----------------
export const useAuditoria = (params?: Params) =>
  useQuery({ queryKey: ["auditoria", params], queryFn: () => get<Auditoria[]>("/auditoria/", params) });
export const useAuditoriaResumen = (params?: Params) =>
  useQuery({ queryKey: ["auditoria-resumen", params], queryFn: () => get<any>("/auditoria/resumen", params) });

// ---------------- Evidencias ----------------
export const useEvidencias = (incidenciaId?: number) =>
  useQuery({
    queryKey: ["evidencias", incidenciaId],
    queryFn: () => get<Evidencia[]>(`/incidencias/${incidenciaId}/evidencias`),
    enabled: !!incidenciaId,
  });

// ---------------- Tarifa ----------------
export const useTarifa = () =>
  useQuery({ queryKey: ["tarifa"], queryFn: () => get<import("@/types").TarifaConfig>("/tarifa/") });

// ---------------- Reportes ----------------
export const useReporte = <T = any>(slug: string, params?: Params, enabled = true) =>
  useQuery({ queryKey: ["reporte", slug, params], queryFn: () => get<T>(`/reportes/${slug}`, params), enabled });

// ---------------- Mutación genérica ----------------
/**
 * Hook genérico de mutación con invalidación de queries.
 * Ej: const m = useApiMutation((b) => api.post('/clientes/', b), ['clientes']);
 */
export function useApiMutation<TVars = any, TData = any>(
  fn: (vars: TVars) => Promise<{ data: TData }>,
  invalidate: string[] = [],
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (vars: TVars) => (await fn(vars)).data,
    onSuccess: () => {
      invalidate.forEach((key) => qc.invalidateQueries({ queryKey: [key] }));
    },
  });
}
