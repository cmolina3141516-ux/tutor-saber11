"""Prepara las imágenes de la pregunta para el modelo.

El banco de la plataforma guarda gráficas y tablas como SVG (data:image/svg+xml), y OpenAI solo
acepta PNG, JPEG, WEBP y GIF: con un SVG la llamada falla y Marco cae al respaldo. Aquí el SVG se
convierte a PNG. Si la conversión no es posible, se manda el texto que contiene el SVG (títulos,
etiquetas y valores), que es mejor que nada.
"""

import base64
import html
import logging
import re
from urllib.parse import unquote

log = logging.getLogger("marco")

# Ancho del PNG: suficiente para leer los números de una gráfica sin gastar tokens de más.
ANCHO_PNG = 1024


def _svg_de_data_url(url: str) -> str | None:
    cabecera, _, datos = url.partition(",")
    if not cabecera.lower().startswith("data:image/svg+xml"):
        return None
    if ";base64" in cabecera.lower():
        return base64.b64decode(datos).decode("utf-8", "replace")
    return unquote(datos)


def _svg_a_png(svg: str) -> bytes:
    import cairosvg  # Necesita libcairo (instalada en la imagen de Cloud Run).

    return cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=ANCHO_PNG)


def _texto_del_svg(svg: str) -> str:
    textos = [html.unescape(re.sub(r"<[^>]+>", "", t)).strip() for t in re.findall(r"<text\b[^>]*>(.*?)</text>", svg, re.S)]
    return " | ".join(t for t in textos if t)


def partes_imagen(url: str, nombre: str) -> list[dict]:
    """Partes de entrada para una imagen: la imagen tal cual, el SVG como PNG, o su texto."""
    svg = _svg_de_data_url(url)
    if svg is None:
        return [{"type": "input_image", "image_url": url, "detail": "auto"}]
    try:
        png = base64.b64encode(_svg_a_png(svg)).decode()
        return [{"type": "input_image", "image_url": f"data:image/png;base64,{png}", "detail": "auto"}]
    except Exception as error:  # noqa: BLE001 — cualquier fallo de conversión cae al texto
        log.warning("No se pudo convertir el SVG de %s a PNG: %s", nombre, error)
        texto = _texto_del_svg(svg)
        return [{"type": "input_text", "text": f"Texto que contiene {nombre} (no se pudo mostrar la imagen): {texto or '(sin texto)'}"}]
