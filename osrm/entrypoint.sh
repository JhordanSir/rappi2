#!/usr/bin/env bash
# Prepara (una sola vez) y sirve OSRM para ruteo por calles, sin API key.
# El mapa procesado se guarda en el volumen /data, así los reinicios son instantáneos.
set -euo pipefail

DATA=/data
PBF="$DATA/region.osm.pbf"
OSRM="$DATA/region.osrm"
URL="${OSRM_REGION_URL:-https://download.geofabrik.de/south-america/peru-latest.osm.pbf}"

if [ ! -f "${OSRM}.mldgr" ]; then
  echo "[osrm] No hay datos procesados. Preparando (descarga + preprocesado; tarda varios minutos la 1ra vez)…"
  if [ ! -f "$PBF" ]; then
    if ! command -v curl >/dev/null 2>&1; then
      apt-get update && apt-get install -y --no-install-recommends curl ca-certificates
    fi
    echo "[osrm] Descargando mapa: $URL"
    curl -L --fail -o "$PBF" "$URL"
  fi
  echo "[osrm] osrm-extract…"
  osrm-extract -p /opt/car.lua "$PBF"
  echo "[osrm] osrm-partition…"
  osrm-partition "$OSRM"
  echo "[osrm] osrm-customize…"
  osrm-customize "$OSRM"
  echo "[osrm] Preprocesado completo."
fi

echo "[osrm] Sirviendo en :5000 (algoritmo MLD)"
exec osrm-routed --algorithm mld --max-table-size 8000 "$OSRM"
