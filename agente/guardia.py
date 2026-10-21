"""Revisa que un mensaje guiado no dé veredictos sobre las opciones.

Marco no recibe la respuesta correcta en las fases guiadas, pero el modelo puede deducirla y
dejarla ver con el tono ("¡bien!", "¿seguro?", "revisa la B"). Esta revisión es la segunda
barrera, después de las instrucciones: si detecta un veredicto, primero intenta quitar una
interjección inicial ("Sí, …", "Exacto. …"); si no basta, se pide otro mensaje o se usa uno fijo.

Las reacciones de acierto o error solo delatan algo desde la fase descarte, cuando ya hay opciones
en juego. En indagacion, un "Sí, eso piden" sobre la lectura del enunciado no dice nada de las
opciones, y bloquearlo dejaba al estudiante con el mensaje fijo.
"""

import re
import unicodedata


def _normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sin_tildes.lower())


# "la B", "la opción B", "opción B"; no "es a" (preposición).
_OPCION = r"(?:(?:la|el) (?:opcion |alternativa |respuesta |literal )?|(?:opcion|alternativa|literal) )[abcd]\b"

# En cualquier fase: calificar opciones o descartes.
SOBRE_OPCIONES = [
    r"\b(?:respuesta|opcion|alternativa)s? (?:es |son |seria |serian )?(?:la |las )?(?:correcta|incorrecta|acertada|equivocada|buena|mala|valida|falsa)s?\b",
    r"\b(?:la|las) (?:correcta|incorrecta)s?\b",
    rf"\b(?:es|seria|sera|debe ser|tiene que ser|parece ser) {_OPCION}",
    rf"\b(?:marca|elige|escoge|quedate con|ve por) {_OPCION}",
    r"\b(?:bien|mal) descartad[ao]s?\b",
    r"\bno (?:la |lo )?descartes\b",
    r"\b(?:no deberias|no debiste) descartar\b",
    rf"\b(?:revisa|reconsidera|vuelve a mirar|mira de nuevo|piensa mejor|repiensa) {_OPCION}",
]

# Interjección de acierto o error al comienzo del mensaje (se puede quitar sin perder el resto).
_INTERJECCION = r"^\W*(?:si|no|correcto|correcta|exacto|exacta|exactamente|perfecto|eso es|asi es|muy bien|bien hecho|excelente|acertaste|incorrecto|no exactamente|casi|uy|ojo)\b[^.,:;!?]*[.,:;!]\s*"

# Desde la fase descarte: reacciones que, ante un descarte, dirían si fue acierto o error.
REACCIONES = [
    r"^\W*(?:si|no)\s*[,.!]",
    r"^\W*(?:correcto|correcta|exacto|exacta|exactamente|perfecto|eso es|asi es|muy bien|bien hecho|excelente|acertaste|incorrecto|no exactamente|casi|uy|ojo)\b",
    r"\b(?:acertaste|te equivocaste|estas equivocad[oa]|vas por (?:buen camino|la idea|ahi)|vas bien|vas mal|vas sumando|en lo cierto)\b",
    r"\bvas \w+ (?:bien|mal)\b",
    r"\b(?:cuidado|estas segur[oa]|seguro que|segura que)\b",
]

_SOBRE_OPCIONES = [re.compile(p) for p in SOBRE_OPCIONES]
_REACCIONES = [re.compile(p) for p in REACCIONES]
_REGEX_INTERJECCION = re.compile(_INTERJECCION)


def da_veredicto(mensaje: str, fase: str = "descarte") -> bool:
    texto = _normalizar(mensaje)
    patrones = _SOBRE_OPCIONES if fase == "indagacion" else _SOBRE_OPCIONES + _REACCIONES
    return any(r.search(texto) for r in patrones)


def quitar_interjeccion(mensaje: str) -> str:
    """Quita una interjección inicial ("Sí, …", "¡Exacto! …") y deja el resto del mensaje."""
    m = _REGEX_INTERJECCION.match(_normalizar(mensaje))
    if not m:
        return mensaje
    # _normalizar conserva la longitud salvo tildes y espacios repetidos: se corta por palabras.
    palabras_a_quitar = len(m.group(0).split())
    resto = " ".join(mensaje.split()[palabras_a_quitar:])
    return resto[:1].upper() + resto[1:] if resto else mensaje
