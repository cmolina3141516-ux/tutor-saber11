"""Revisa que un mensaje guiado no dé veredictos sobre las opciones.

Marco no recibe la respuesta correcta en las fases guiadas, pero el modelo puede deducirla y
dejarla ver con el tono ("¡bien!", "¿seguro?", "revisa la B"). Esta revisión es la segunda
barrera, después de las instrucciones: si detecta un veredicto, se pide otro mensaje o se usa uno
fijo. Prefiere equivocarse por exceso: un mensaje neutro de más no hace daño.
"""

import re
import unicodedata


def _normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sin_tildes.lower())


# "la B", "la opción B", "opción B"; no "es a" (preposición).
_OPCION = r"(?:(?:la|el) (?:opcion |alternativa |respuesta |literal )?|(?:opcion|alternativa|literal) )[abcd]\b"

PATRONES = [
    # Calificar una respuesta u opción.
    r"\b(?:respuesta|opcion|alternativa)s? (?:es |son |seria |serian )?(?:la |las )?(?:correcta|incorrecta|acertada|equivocada|buena|mala|valida|falsa)s?\b",
    r"\b(?:la|las) (?:correcta|incorrecta)s?\b",
    rf"\b(?:es|seria|sera|debe ser|tiene que ser|parece ser) {_OPCION}",
    rf"\b(?:marca|elige|escoge|quedate con|ve por) {_OPCION}",
    # Calificar un descarte.
    r"\b(?:bien|mal) descartad[ao]s?\b",
    r"\bno (?:la |lo )?descartes\b",
    r"\b(?:no deberias|no debiste) descartar\b",
    rf"\b(?:revisa|reconsidera|vuelve a mirar|mira de nuevo|piensa mejor|repiensa) {_OPCION}",
    # Interjecciones de acierto o error al reaccionar.
    r"^\W*(?:si|no)\s*[,.!]",
    r"^\W*(?:correcto|correcta|exacto|exacta|exactamente|perfecto|eso es|asi es|muy bien|bien hecho|excelente|acertaste|incorrecto|no exactamente|casi|uy|ojo)\b",
    r"\b(?:acertaste|te equivocaste|estas equivocad[oa]|vas por (?:buen camino|la idea|ahi)|vas bien|vas mal|vas sumando|en lo cierto)\b",
    r"\b(?:cuidado|estas segur[oa]|seguro que|segura que)\b",
]

_REGEX = [re.compile(p) for p in PATRONES]


def da_veredicto(mensaje: str) -> bool:
    texto = _normalizar(mensaje)
    return any(r.search(texto) for r in _REGEX)
