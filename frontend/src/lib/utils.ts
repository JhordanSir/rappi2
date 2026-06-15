import { clsx, type ClassValue } from "clsx";

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export function formatMoney(value?: number | string | null, currency = "PEN"): string {
  if (value === null || value === undefined || value === "") return "—";
  const n = typeof value === "string" ? Number(value) : value;
  if (Number.isNaN(n)) return "—";
  return new Intl.NumberFormat("es-PE", { style: "currency", currency }).format(n);
}

export function formatNumber(value?: number | null, digits = 0): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("es-PE", { maximumFractionDigits: digits }).format(value);
}

export function formatDate(value?: string | null, withTime = true): string {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("es-PE", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } : {}),
  });
}

export function timeAgo(value?: string | null): string {
  if (!value) return "—";
  const d = new Date(value).getTime();
  const diff = Date.now() - d;
  const sec = Math.round(diff / 1000);
  if (sec < 60) return `hace ${sec}s`;
  const min = Math.round(sec / 60);
  if (min < 60) return `hace ${min}m`;
  const h = Math.round(min / 60);
  if (h < 24) return `hace ${h}h`;
  const days = Math.round(h / 24);
  return `hace ${days}d`;
}

export function formatCoord(lat?: number | null, lon?: number | null): string {
  if (lat === null || lat === undefined || lon === null || lon === undefined) return "Sin coordenadas";
  return `${Number(lat).toFixed(5)}, ${Number(lon).toFixed(5)}`;
}

/** Segundos -> "1h 23m" */
export function humanDuration(seconds?: number | null): string {
  if (seconds === null || seconds === undefined) return "—";
  const s = Math.round(seconds);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m`;
  return `${s}s`;
}

/** Ray-casting: ¿el punto [lat,lon] está dentro del polígono (anillo de [lat,lon])? */
export function pointInPolygon(point: [number, number], polygon: [number, number][]): boolean {
  const y = point[0]; // lat
  const x = point[1]; // lon
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const yi = polygon[i][0];
    const xi = polygon[i][1];
    const yj = polygon[j][0];
    const xj = polygon[j][1];
    const intersect = yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

export function initials(name?: string | null): string {
  if (!name) return "?";
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("");
}
