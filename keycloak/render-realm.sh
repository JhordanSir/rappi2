#!/bin/sh
# Genera el realm a importar (realm-rappi2.json) a partir de la plantilla, sustituyendo
# desde el entorno el dominio público del frontend (redirectUris/webOrigins) y la
# configuración SMTP usada por Keycloak para enviar los correos de recuperación de
# contraseña ("¿Olvidaste tu contraseña?"). Se hace aquí porque la sustitución nativa de
# variables en el import de Keycloak no es fiable.
#
# Sustitución LITERAL y segura: escapamos \, & y el delimitador | antes de pasarlos a sed,
# para que contraseñas/claves con caracteres especiales no rompan el comando (evita usar
# `"` y `\` en SMTP_PASSWORD: romperían el JSON resultante).
set -eu

esc() {
  # Escapa la parte de reemplazo de sed: primero \, luego & y el delimitador |.
  printf '%s' "${1:-}" | sed -e 's/\\/\\\\/g' -e 's/&/\\&/g' -e 's/|/\\|/g'
}

FRONTEND_URL="${FRONTEND_URL:-http://localhost:5173}"
SMTP_HOST="${SMTP_HOST:-}"
SMTP_PORT="${SMTP_PORT:-587}"
SMTP_USER="${SMTP_USER:-}"
SMTP_PASSWORD="${SMTP_PASSWORD:-}"
# Si no se define un remitente explícito, usa el usuario SMTP.
SMTP_FROM="${SMTP_FROM:-$SMTP_USER}"
SMTP_FROM_DISPLAY="${SMTP_FROM_DISPLAY:-Rappi2}"
SMTP_STARTTLS="${SMTP_STARTTLS:-true}"
SMTP_SSL="${SMTP_SSL:-false}"
SMTP_AUTH="${SMTP_AUTH:-true}"

sed \
  -e "s|__FRONTEND_URL__|$(esc "$FRONTEND_URL")|g" \
  -e "s|__SMTP_HOST__|$(esc "$SMTP_HOST")|g" \
  -e "s|__SMTP_PORT__|$(esc "$SMTP_PORT")|g" \
  -e "s|__SMTP_FROM__|$(esc "$SMTP_FROM")|g" \
  -e "s|__SMTP_FROM_DISPLAY__|$(esc "$SMTP_FROM_DISPLAY")|g" \
  -e "s|__SMTP_USER__|$(esc "$SMTP_USER")|g" \
  -e "s|__SMTP_PASSWORD__|$(esc "$SMTP_PASSWORD")|g" \
  -e "s|__SMTP_STARTTLS__|$(esc "$SMTP_STARTTLS")|g" \
  -e "s|__SMTP_SSL__|$(esc "$SMTP_SSL")|g" \
  -e "s|__SMTP_AUTH__|$(esc "$SMTP_AUTH")|g" \
  /template/realm-rappi2.template.json > /import/realm-rappi2.json

if [ -n "$SMTP_HOST" ]; then
  echo "[keycloak-config] realm-rappi2.json generado con SMTP en ${SMTP_HOST}:${SMTP_PORT} (remitente: ${SMTP_FROM:-<sin remitente>})."
else
  echo "[keycloak-config] realm-rappi2.json generado SIN SMTP (define SMTP_HOST en el .env para habilitar el envío de correos de recuperación)."
fi
