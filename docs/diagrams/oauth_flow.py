"""Genera el diagrama de arquitectura del flujo OAuth 2.0 (Authorization Code + PKCE) de Rappi2.

Salida: ``docs/arquitectura_oauth.png``.

El flujo dibujado es el REALMENTE implementado: cliente público SPA (React + keycloak-js)
que hace el intercambio *code → token* contra Keycloak con PKCE en el navegador; el backend
FastAPI **solo valida** el access token contra el JWKS de Keycloak (no emite tokens ni hace el
canje server-to-server) y aplica ownership por `sub`.

Requisitos (ver docs/diagrams/README.md):
  - Binario Graphviz en el PATH (provee `dot`).  Windows: `winget install Graphviz.Graphviz`
  - Paquetes Python: `pip install diagrams graphviz pillow`

Uso:
  python docs/diagrams/oauth_flow.py
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
DOCS_DIR = HERE.parent
ASSETS = HERE / "assets"
KEYCLOAK_ICON = ASSETS / "keycloak.png"
OUT_BASENAME = DOCS_DIR / "arquitectura_oauth"  # diagrams añade la extensión .png


def _ensure_dot_on_path() -> None:
    """Si `dot` no está en el PATH, intenta ubicaciones típicas de Graphviz en Windows.

    No es un hardcode exclusivo: solo AUGMENTA el PATH cuando el binario no se encuentra
    (p. ej. shell abierta antes de instalar Graphviz). En Linux/Mac normalmente ya está.
    """
    if shutil.which("dot"):
        return
    candidatos = [
        r"C:\Program Files\Graphviz\bin",
        r"C:\Program Files (x86)\Graphviz\bin",
    ]
    for c in candidatos:
        if Path(c, "dot.exe").exists():
            os.environ["PATH"] = c + os.pathsep + os.environ.get("PATH", "")
            return


def _ensure_keycloak_icon() -> Path:
    """Genera un ícono local para Keycloak si no existe (evita depender de red/logos externos).

    Dibuja un escudo con una cerradura sobre el azul corporativo de Keycloak. Es un ícono
    representativo (no el logo oficial), suficiente para identificar el nodo en el diagrama.
    """
    if KEYCLOAK_ICON.exists():
        return KEYCLOAK_ICON
    ASSETS.mkdir(parents=True, exist_ok=True)
    from PIL import Image, ImageDraw

    size = 512
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    azul = (0, 106, 168, 255)      # azul Keycloak
    azul_osc = (0, 74, 122, 255)
    blanco = (255, 255, 255, 255)

    # Escudo (polígono)
    m = 56
    escudo = [
        (size // 2, m),
        (size - m, m + 90),
        (size - m, size // 2 + 40),
        (size // 2, size - m),
        (m, size // 2 + 40),
        (m, m + 90),
    ]
    d.polygon(escudo, fill=azul, outline=azul_osc, width=10)

    # Cerradura: círculo + cuerpo
    cx, cy = size // 2, size // 2 - 10
    r = 66
    d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=blanco, width=34)
    d.rectangle([cx - 26, cy + 40, cx + 26, cy + 150], fill=blanco)
    img.save(KEYCLOAK_ICON)
    return KEYCLOAK_ICON


def build() -> Path:
    _ensure_dot_on_path()
    if not shutil.which("dot"):
        raise SystemExit(
            "No se encontró 'dot' (Graphviz). Instálalo: winget install Graphviz.Graphviz "
            "y reabre la terminal, o consulta docs/diagrams/README.md."
        )
    icon = _ensure_keycloak_icon()

    # Importar aquí para que el mensaje de ayuda de arriba se muestre sin traceback feo.
    from diagrams import Cluster, Diagram, Edge
    from diagrams.custom import Custom
    from diagrams.onprem.database import MongoDB, PostgreSQL
    from diagrams.onprem.inmemory import Redis
    from diagrams.programming.framework import FastAPI, React

    graph_attr = {
        "fontsize": "20",
        "labelloc": "t",
        "pad": "0.6",
        "nodesep": "0.7",
        "ranksep": "1.1",
        "bgcolor": "white",
        "splines": "spline",
    }
    node_attr = {"fontsize": "12"}

    with Diagram(
        "Rappi2 — Flujo OAuth 2.0 Authorization Code + PKCE (Keycloak / OIDC)",
        filename=str(OUT_BASENAME),
        outformat="png",
        show=False,
        direction="TB",
        graph_attr=graph_attr,
        node_attr=node_attr,
    ):
        with Cluster("Navegador del usuario"):
            spa = React("Frontend SPA\n(React + keycloak-js)")

        keycloak = Custom("Keycloak\n(Authorization Server · OIDC)", str(icon))

        with Cluster("Servidor de aplicación"):
            backend = FastAPI("Backend API\n(FastAPI · valida JWT)")

        with Cluster("Persistencia"):
            postgres = PostgreSQL("PostgreSQL\n(usuarios, roles,\npermisos, dominio)")
            mongo = MongoDB("MongoDB\n(tracking, evidencias,\nnotif., auditoría)")
            redis = Redis("Redis\n(SSE pub/sub)")

        # --- Flujo OAuth (Authorization Code + PKCE) — pasos numerados ---
        # El canje code->token ocurre en el NAVEGADOR (cliente público + PKCE).
        spa >> Edge(label="1. login + consent\n(Authorization Code + PKCE, S256)", color="#1d4ed8", fontcolor="#1d4ed8") >> keycloak
        keycloak >> Edge(label="2. redirect con code", color="#1d4ed8", fontcolor="#1d4ed8", style="dashed") >> spa
        spa >> Edge(label="3. code + code_verifier\n→ access token (RS256)", color="#1d4ed8", fontcolor="#1d4ed8") >> keycloak

        # Request con Bearer y respuesta sobre el MISMO enlace (evita etiquetas superpuestas).
        spa >> Edge(
            label="4. request + Authorization: Bearer\n7. respuesta JSON (solo datos del dueño · sub)",
            color="#059669", fontcolor="#059669", dir="both",
        ) >> backend
        backend >> Edge(label="5. valida firma/iss/aud/exp\nvía JWKS (cacheado)", color="#b45309", fontcolor="#b45309", style="dashed") >> keycloak

        # Ownership por sub + carga de rol/permisos.
        backend >> Edge(label="6. provisiona/enlaza por sub,\ncarga rol + permisos", color="#7c3aed", fontcolor="#7c3aed") >> postgres

        # Contexto (no forma parte del flujo OAuth): otras persistencias.
        backend >> Edge(color="#9ca3af", style="dotted") >> mongo
        backend >> Edge(color="#9ca3af", style="dotted") >> redis

    out = OUT_BASENAME.with_suffix(".png")
    print(f"OK -> {out}")
    return out


if __name__ == "__main__":
    build()
