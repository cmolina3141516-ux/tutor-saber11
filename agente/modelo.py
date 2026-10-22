"""Llamada a OpenAI (gpt-5.4-mini por defecto) con salida JSON estructurada."""

import json
import os
from functools import lru_cache

import openai

MODELO = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
# La plataforma espera 20 s como máximo; dejamos margen para un reintento corto y la red.
TIEMPO_MAXIMO_S = float(os.getenv("OPENAI_TIMEOUT_S", "14"))
ESFUERZO_GUIA = os.getenv("REASONING_EFFORT_GUIDE", "low")
ESFUERZO_REVISION = os.getenv("REASONING_EFFORT_REVIEW", "low")
# El informe de la prueba corta analiza 10 preguntas juntas: un poco más de razonamiento.
ESFUERZO_INFORME = os.getenv("REASONING_EFFORT_REPORT", "medium")


class ErrorModelo(Exception):
    pass


@lru_cache(maxsize=1)
def _cliente() -> openai.OpenAI:
    if not os.getenv("OPENAI_API_KEY"):
        raise ErrorModelo("Falta OPENAI_API_KEY")
    return openai.OpenAI(timeout=TIEMPO_MAXIMO_S, max_retries=0)


def pedir_json(
    *,
    instrucciones: str,
    contenido: list[dict],
    esquema: dict,
    nombre: str,
    esfuerzo: str,
    max_tokens: int,
    timeout: float | None = None,
) -> dict:
    """Devuelve el JSON que produjo el modelo, ya validado contra `esquema` por OpenAI."""
    try:
        respuesta = _cliente().responses.create(
            model=MODELO,
            instructions=instrucciones,
            input=[{"role": "user", "content": contenido}],
            text={"format": {"type": "json_schema", "name": nombre, "schema": esquema, "strict": True}},
            reasoning={"effort": esfuerzo},
            max_output_tokens=max_tokens,
            # Las instrucciones fijas se reutilizan del caché entre estudiantes.
            prompt_cache_key=f"marco-{nombre}",
            # No guardamos las conversaciones de menores en OpenAI.
            store=False,
            **({"timeout": timeout} if timeout else {}),
        )
    except openai.OpenAIError as error:
        raise ErrorModelo(f"{type(error).__name__}: {error}") from error
    try:
        return json.loads(respuesta.output_text)
    except (json.JSONDecodeError, TypeError) as error:
        raise ErrorModelo(f"Respuesta sin JSON válido (estado {respuesta.status})") from error
