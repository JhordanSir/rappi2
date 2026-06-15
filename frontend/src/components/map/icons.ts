import L from "leaflet";

/** Pin SVG como divIcon (evita el problema de assets de marker en Vite). */
export function pinIcon(color: string, label?: string): L.DivIcon {
  const inner = label
    ? `<span style="position:absolute;top:5px;left:0;right:0;text-align:center;color:#fff;font-size:11px;font-weight:700">${label}</span>`
    : "";
  return L.divIcon({
    className: "",
    html: `<div style="position:relative;width:28px;height:38px;filter:drop-shadow(0 2px 3px rgba(0,0,0,.35))">
      <svg width="28" height="38" viewBox="0 0 28 38" xmlns="http://www.w3.org/2000/svg">
        <path d="M14 0C6.27 0 0 6.16 0 13.76 0 23.2 14 38 14 38s14-14.8 14-24.24C28 6.16 21.73 0 14 0z" fill="${color}"/>
        <circle cx="14" cy="14" r="5.2" fill="#fff"/>
      </svg>${inner}
    </div>`,
    iconSize: [28, 38],
    iconAnchor: [14, 38],
    popupAnchor: [0, -34],
  });
}

/** Punto pulsante para la posición en vivo del conductor. */
export function liveIcon(color = "#0d9488"): L.DivIcon {
  return L.divIcon({
    className: "",
    html: `<div style="position:relative;width:18px;height:18px">
      <span style="position:absolute;inset:0;border-radius:9999px;background:${color};opacity:.3;animation:ping 1.4s cubic-bezier(0,0,.2,1) infinite"></span>
      <span style="position:absolute;inset:4px;border-radius:9999px;background:${color};border:2px solid #fff"></span>
    </div>
    <style>@keyframes ping{75%,100%{transform:scale(2.2);opacity:0}}</style>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
  });
}

export const COLORS = {
  origen: "#10b981",
  destino: "#f43f5e",
  parada: "#d97706",
  live: "#0d9488",
  conductor: "#0d9488",
  brand: "#0d9488",
};
