# Diagramas generados por código

## Flujo OAuth 2.0 (Authorization Code + PKCE)

[`oauth_flow.py`](oauth_flow.py) genera [`../arquitectura_oauth.png`](../arquitectura_oauth.png):
el diagrama de **componentes + BDs + flujo OAuth** tal como está implementado (cliente público
SPA que canjea `code → token` con Keycloak vía PKCE; el backend FastAPI **solo valida** el
access token contra el JWKS de Keycloak y aplica ownership por `sub`).

### Requisitos

1. **Binario Graphviz** en el `PATH` (provee `dot`):
   - Windows: `winget install Graphviz.Graphviz` (y reabre la terminal), o `choco install graphviz`.
   - Debian/Ubuntu: `sudo apt-get install graphviz` · macOS: `brew install graphviz`.
   - En Windows, si abriste la terminal **antes** de instalar Graphviz, el script intenta
     además las rutas típicas (`C:\Program Files\Graphviz\bin`) automáticamente.
2. **Paquetes Python**: `pip install diagrams graphviz pillow`.

### Regenerar

```bash
python docs/diagrams/oauth_flow.py
# OK -> docs/arquitectura_oauth.png
```

### Notas

- `assets/keycloak.png` es un ícono representativo que el script **genera solo** con Pillow
  si no existe (no es el logo oficial; evita depender de red o de licencias de terceros).
- La imagen se embebe en la sección *Arquitectura* del [README](../../README.md) principal.
