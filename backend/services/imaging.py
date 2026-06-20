"""Compresión de imágenes para evidencia/incidencias antes de guardarlas en GridFS.

Estándar de la industria para fotos de prueba: re-encodear a JPEG progresivo de calidad
~82, limitar la dimensión mayor a 1600 px, respetar la orientación EXIF (y luego
descartar metadatos). Solo se aplica a imágenes rasterizadas; otros archivos
(video/audio/PDF) se guardan tal cual. Si la compresión no reduce el tamaño, se conserva
el original (p.ej. JPEG ya optimizado).
"""
import logging
import os
from io import BytesIO

logger = logging.getLogger(__name__)

MAX_DIM = 1600          # lado mayor en píxeles
JPEG_QUALITY = 82
# Formatos rasterizados que conviene recomprimir (no GIF/SVG/animaciones).
_RECOMPRIMIBLES = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/bmp", "image/tiff"}


def comprimir_imagen(contenido: bytes, content_type: str | None, filename: str | None) -> tuple[bytes, str, str]:
    """Devuelve (bytes, content_type, filename) ya comprimidos. No-op para no-imágenes."""
    ct = (content_type or "").lower().split(";")[0].strip()
    nombre = filename or "archivo"
    if ct not in _RECOMPRIMIBLES:
        return contenido, content_type or "application/octet-stream", nombre
    try:
        from PIL import Image, ImageOps

        with Image.open(BytesIO(contenido)) as img:
            img = ImageOps.exif_transpose(img)  # aplica orientación y descarta EXIF
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            img.thumbnail((MAX_DIM, MAX_DIM), Image.LANCZOS)
            out = BytesIO()
            img.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
        data = out.getvalue()
        if len(data) >= len(contenido):
            return contenido, content_type or "image/jpeg", nombre
        base = os.path.splitext(nombre)[0] or "imagen"
        return data, "image/jpeg", f"{base}.jpg"
    except Exception as exc:  # noqa: BLE001 - nunca rompe la subida por la compresión
        logger.warning("No se pudo comprimir la imagen %s: %s", nombre, exc)
        return contenido, content_type or "application/octet-stream", nombre
