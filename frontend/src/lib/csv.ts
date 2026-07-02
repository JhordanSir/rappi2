/** Exportación CSV client-side: convierte filas ya cargadas en la página y dispara
 *  la descarga. Con BOM UTF-8 para que Excel abra bien tildes y eñes. */

function escapar(v: unknown): string {
  if (v === null || v === undefined) return "";
  const s = String(v);
  // Comillas dobles, comas o saltos de línea → campo entre comillas (RFC 4180).
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/** Genera el texto CSV a partir de filas homogéneas (usa las claves de la primera). */
export function toCSV(filas: Record<string, unknown>[], columnas?: string[]): string {
  if (filas.length === 0) return "";
  const cols = columnas ?? Object.keys(filas[0]);
  const lineas = [cols.join(",")];
  for (const fila of filas) {
    lineas.push(cols.map((c) => escapar(fila[c])).join(","));
  }
  return lineas.join("\r\n");
}

/** Descarga `filas` como archivo CSV (`nombre.csv`). No hace nada si no hay filas. */
export function descargarCSV(nombre: string, filas: Record<string, unknown>[], columnas?: string[]): void {
  const csv = toCSV(filas, columnas);
  if (!csv) return;
  const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nombre.endsWith(".csv") ? nombre : `${nombre}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}
