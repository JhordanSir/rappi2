// Tipos alineados con los schemas Pydantic del backend (rappi2).

export type EstadoOrden = "Pendiente" | "En Proceso" | "En Tránsito" | "Entregado" | "Cancelado";
export type EstadoVehiculo = "Operativo" | "Mantenimiento" | "Inactivo";
export type DisponibilidadConductor = "Disponible" | "Ocupado" | "Inactivo";
export type EstadoAsignacion = "Asignada" | "EnCurso" | "Finalizada" | "Cancelada";
export type EstadoParada = "Pendiente" | "Visitada" | "Omitida";
export type EstadoPago = "Pendiente" | "Pagado" | "Fallido" | "Reembolsado";
export type TipoEvidencia = "foto" | "video" | "audio" | "documento";

// ---- Auth / RBAC ----
export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface Permiso {
  id: number;
  rol_id: number;
  recurso: string;
  accion: string;
}

export interface Rol {
  id: number;
  nombre: string;
  permisos: Permiso[];
}

export interface Usuario {
  id: number;
  username: string;
  email: string;
  rol_id: number;
  cliente_id?: number | null;
  activo: boolean;
  fecha_registro: string;
  rol?: Rol | null;
}

// ---- Clientes ----
export interface ClienteDireccion {
  id: number;
  cliente_id: number;
  direccion: string;
  distrito?: string | null;
  ciudad?: string | null;
  estado?: string | null;
  pais?: string | null;
  lat?: number | null;
  lon?: number | null;
  es_principal: boolean;
}

export interface Cliente {
  id: number;
  nombre: string;
  email: string;
  telefono?: string | null;
  cc_id?: string | null;
  activo: boolean;
  fecha_registro: string;
  direcciones: ClienteDireccion[];
}

// ---- Ordenes ----
export interface Orden {
  id: number;
  cliente_id: number;
  estado: EstadoOrden;
  direccion_origen: string;
  distrito_origen?: string | null;
  lat_origen?: number | null;
  lon_origen?: number | null;
  direccion_destino: string;
  distrito_destino?: string | null;
  lat_destino?: number | null;
  lon_destino?: number | null;
  total?: number | null;
  fecha_creacion: string;
}

// ---- Vehiculos / Conductores ----
export interface Vehiculo {
  placa: string;
  tipo: string;
  capacidad_kg: number;
  estado: EstadoVehiculo;
  fecha_mantenimiento?: string | null;
  activo: boolean;
}

export interface Conductor {
  id: number;
  usuario_id: number;
  nombre: string;
  licencia: string;
  disponibilidad: DisponibilidadConductor;
  vehiculo_placa?: string | null;
  activo: boolean;
  vehiculo?: Vehiculo | null;
}

// ---- Asignaciones ----
export interface Asignacion {
  id: number;
  orden_id: number;
  conductor_id: number;
  vehiculo_placa: string;
  estado: EstadoAsignacion;
  fecha_inicio?: string | null;
  fecha_fin?: string | null;
  entrega_lat?: number | null;
  entrega_lon?: number | null;
  entrega_receptor?: string | null;
}

// ---- Rutas / Paradas ----
export interface Parada {
  id: number;
  ruta_id: number;
  orden_id?: number | null;
  direccion: string;
  distrito?: string | null;
  lat?: number | null;
  lon?: number | null;
  secuencia: number;
  estado: EstadoParada;
  fecha_paso?: string | null;
}

export interface Ruta {
  id: number;
  orden_id: number;
  distancia_km?: number | null;
  tiempo_estimado?: string | null;
  paradas: Parada[];
}

// ---- Incidencias ----
export interface Incidencia {
  id: number;
  asignacion_id: number;
  tipo: string;
  severidad: number;
  notas?: string | null;
  evidencia_url?: string | null;
  fecha: string;
}

// ---- Pagos / Facturas ----
export interface Pago {
  id: number;
  orden_id: number;
  fecha_pago: string;
  monto: number;
  estado: EstadoPago;
  referencia_banco?: string | null;
}

export interface Factura {
  id: number;
  orden_id: number;
  fecha: string;
  ruc?: string | null;
  monto: number;
  url?: string | null;
}

// ---- Tracking / Seguimiento ----
export interface GPSPing {
  id: string;
  asignacion_id: number;
  conductor_id: number;
  vehiculo_placa: string;
  location: { type: string; coordinates: [number, number] };
  speed_kmh?: number | null;
  heading?: number | null;
  accuracy_m?: number | null;
  timestamp: string;
}

export interface PuntoGeo {
  direccion?: string | null;
  distrito?: string | null;
  lat?: number | null;
  lon?: number | null;
}

export interface PosicionActual {
  lat: number;
  lon: number;
  speed_kmh?: number | null;
  heading?: number | null;
  timestamp: string;
}

export interface ParadaSeguimiento {
  id: number;
  secuencia: number;
  direccion: string;
  lat?: number | null;
  lon?: number | null;
  estado: string;
  fecha_paso?: string | null;
}

export interface AsignacionSeguimiento {
  id: number;
  estado: string;
  conductor_id: number;
  conductor_nombre?: string | null;
  vehiculo_placa?: string | null;
  fecha_inicio?: string | null;
  fecha_fin?: string | null;
}

export interface RutaSeguimiento {
  id: number;
  distancia_km?: number | null;
  tiempo_estimado_segundos?: number | null;
}

export interface Geocerca {
  id: string;
  ruta_id?: number | null;
  orden_id?: number | null;
  tipo: string;
  geometry: { type: string; coordinates: number[][][] | number[][] };
  tolerance_m?: number | null;
  activa: boolean;
  created_at: string;
}

export interface OrdenSeguimiento {
  orden_id: number;
  estado: string;
  cliente_id: number;
  origen: PuntoGeo;
  destino: PuntoGeo;
  asignacion?: AsignacionSeguimiento | null;
  posicion_actual?: PosicionActual | null;
  ruta?: RutaSeguimiento | null;
  paradas: ParadaSeguimiento[];
  geocercas: Geocerca[];
  estadisticas?: Record<string, any> | null;
}

// ---- Notificaciones ----
export interface Notificacion {
  id: string;
  destinatario_tipo: "usuario" | "cliente";
  destinatario_id: number;
  tipo: string;
  titulo: string;
  mensaje: string;
  metadata: Record<string, any>;
  leida: boolean;
  fecha: string;
}

// ---- Auditoría ----
export interface Auditoria {
  id: string;
  usuario_id?: number | null;
  ruta: string;
  metodo: string;
  ip?: string | null;
  status_code: number;
  payload_hash?: string | null;
  timestamp: string;
}

// ---- Sesiones ----
export interface TokenInfo {
  id: number;
  usuario_id: number;
  fecha_expiracion: string;
  revocado: boolean;
}

// ---- Evidencias ----
export interface ArchivoRef {
  file_id: string;
  filename: string;
  content_type?: string | null;
  size: number;
}

export interface Evidencia {
  id: string;
  incidencia_id: number;
  urls: string[];
  archivos: ArchivoRef[];
  tipo: TipoEvidencia;
  descripcion?: string | null;
  uploaded_by?: number | null;
  timestamp: string;
}

// ---- Reportes ----
export interface DashboardKPIs {
  totales: Record<string, number>;
  ordenes_por_estado: Record<string, number>;
  conductores_por_disponibilidad: Record<string, number>;
  vehiculos_por_estado: Record<string, number>;
  recaudacion_ultimas_24h: number;
  incidencias_severidad_alta: number;
  [k: string]: any;
}
