"""Servicio HTTP de Marco (contrato v4: entrenamiento en dos vueltas).

La plataforma hace POST a la raíz en la segunda vuelta con uno de cuatro modos y espera el JSON
del contrato en menos de 20 s:
  hint          -> indicio mayéutico inicial               -> {"reply"}
  guide         -> respuesta a un mensaje del estudiante   -> {"reply"}
  key_question  -> la Pregunta clave                       -> {"reply"}
  review        -> revisión tras la decisión final         -> {"review"}
En los tres primeros no viajan ni la respuesta correcta ni la de la primera vuelta.
"""

import hmac
import logging
import os
import time

from fastapi import FastAPI, Header, HTTPException
from pydantic import TypeAdapter

from . import instrucciones as ins
from .contrato import (
    Base,
    Peticion,
    PeticionGuia,
    PeticionIndicio,
    PeticionPreguntaClave,
    PeticionRevision,
    Pregunta,
    RespuestaMensaje,
    RespuestaRevision,
)
from .guardia import da_veredicto, quitar_interjeccion
from .imagenes import partes_imagen
from .modelo import ESFUERZO_GUIA, ESFUERZO_REVISION, ErrorModelo, pedir_json
from .perfil import resumen_perfil
from .respaldo import respaldo_guiado, revision_respaldo

log = logging.getLogger("marco")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(levelname)s %(name)s %(message)s")

# Debe coincidir con TUTOR_AGENT_KEY de la plataforma. Vacía = sin llave (solo para pruebas locales).
LLAVE = os.getenv("TUTOR_AGENT_KEY", "")
# Mensajes de la conversación que se le pasan al modelo (los más recientes).
MAX_HISTORIAL = 16
MAX_CARACTERES_MENSAJE = 800
# La plataforma corta a los 20 s; dejamos margen para la red.
PLAZO_PLATAFORMA_S = 17.0
# Si el primer intento tardó más que esto, no hay tiempo para pedir otro mensaje.
TIEMPO_PARA_REINTENTAR_S = 7.0
# En la segunda vuelta el estudiante puede contar qué marcó: cualquier reacción sería un veredicto.
FASE_GUARDIA = "segunda_vuelta"

app = FastAPI(title="Marco, tutor socrático Saber 11", docs_url=None, redoc_url=None)
_peticion = TypeAdapter(Peticion)


def _autorizar(authorization: str | None) -> None:
    if not LLAVE:
        return
    esperado = f"Bearer {LLAVE}"
    if not authorization or not hmac.compare_digest(authorization.encode(), esperado.encode()):
        raise HTTPException(status_code=401, detail="No autorizado")


def _recortar(texto: str, limite: int = MAX_CARACTERES_MENSAJE) -> str:
    texto = texto.strip()
    return texto if len(texto) <= limite else texto[:limite] + "…"


def _contenido_pregunta(q: Pregunta) -> tuple[str, list[dict]]:
    """Texto de la pregunta y las imágenes (contexto y enunciado) como partes de entrada."""
    partes = [
        f"Área: {q.subject}",
        f"Competencia: {q.competencia or 'sin indicar'}",
        f"Componente: {q.component or 'sin indicar'}",
        f"Tema: {q.topic or 'sin indicar'}",
    ]
    imagenes: list[dict] = []
    if q.context:
        partes.append(f"\nTexto o gráfico compartido — {q.context.title}:\n{q.context.text}".rstrip())
        if q.context.imageUrl:
            imagenes += partes_imagen(q.context.imageUrl, "la imagen del contexto")
            partes.append("(La imagen del contexto va adjunta.)")
    partes.append(f"\nEnunciado:\n{q.text or '(el enunciado está en la imagen adjunta)'}")
    if q.imageUrl:
        imagenes += partes_imagen(q.imageUrl, "la imagen del enunciado")
        partes.append("(La imagen del enunciado va adjunta.)")
    partes.append("\nOpciones:")
    partes += [f"{o}. {q.optionTexts.get(o, '(ver imagen)')}" for o in q.options]
    return "\n".join(partes), imagenes


def _conversacion(p: Base) -> str:
    recientes = p.history[-MAX_HISTORIAL:]
    if not recientes:
        return "(todavía no hay conversación)"
    quien = {"student": "Estudiante", "tutor": "Marco"}
    return "\n".join(f"{quien[m.role]}: {_recortar(m.text)}" for m in recientes)


def _material(p: Base) -> str:
    textos = [t for t in p.supportTexts if t.text.strip()]
    if not textos:
        return ""
    cuerpo = "\n\n".join(f"{t.title}:\n{_recortar(t.text, 800)}" for t in textos[:3])
    return (
        "## Material de apoyo del tema (escrito por el profesor)\n"
        "Úsalo para que tu mayéutica vaya en la misma línea. No lo copies ni lo resumas al estudiante.\n"
        f"{cuerpo}"
    )


# ---------- Modos guiados: hint, guide, key_question ----------

def _tarea(p) -> str:
    if isinstance(p, PeticionIndicio):
        return "Modo: hint. Da el indicio conceptual inicial de esta pregunta y termina con una pregunta orientadora."
    if isinstance(p, PeticionPreguntaClave):
        return "Modo: key_question. Escribe la Pregunta clave (empieza con \"Pregunta clave:\")."
    if p.repliesLeft > 0:
        return f"Modo: guide. Responde al mensaje del estudiante. Te quedan {p.repliesLeft} respuesta(s) después de esta."
    return "Modo: guide. Responde al mensaje del estudiante. Te quedan 0 respuestas después de esta: es tu último mensaje, invítalo a decidir."


def _entrada_guiada(p, aviso: str = "") -> list[dict]:
    texto_pregunta, imagenes = _contenido_pregunta(p.question)
    mensaje = (
        f"## Mensaje nuevo del estudiante\n<mensaje_estudiante>\n{_recortar(p.studentMessage, 1500)}\n</mensaje_estudiante>"
        if isinstance(p, PeticionGuia) else ""
    )
    texto = "\n\n".join(filter(None, [
        f"## Pregunta (no conoces la respuesta correcta ni la que marcó el estudiante)\n{texto_pregunta}",
        _material(p),
        f"## Perfil del estudiante\n{resumen_perfil(p.student, p.question.subject, p.question.component)}",
        f"## Conversación hasta ahora\n<conversacion>\n{_conversacion(p)}\n</conversacion>",
        mensaje,
        f"## Tu tarea en este turno\n{_tarea(p)}",
        aviso,
    ]))
    return [{"type": "input_text", "text": texto}, *imagenes]


def _pedir_mensaje(p, aviso: str = "", timeout: float | None = None) -> str:
    salida = pedir_json(
        instrucciones=ins.INSTRUCCIONES_GUIA,
        contenido=_entrada_guiada(p, aviso),
        esquema=ins.ESQUEMA_RESPUESTA,
        nombre="mensaje_guiado",
        esfuerzo=ESFUERZO_GUIA,
        max_tokens=1500,
        timeout=timeout,
    )
    return salida["reply"].strip()


def _limpiar(mensaje: str) -> str:
    """Quita una interjección inicial ("Sí, …") si con eso el mensaje deja de ser un veredicto."""
    if da_veredicto(mensaje, FASE_GUARDIA):
        sin = quitar_interjeccion(mensaje)
        if not da_veredicto(sin, FASE_GUARDIA):
            return sin
    return mensaje


def mensaje_guiado(p: PeticionIndicio | PeticionGuia | PeticionPreguntaClave) -> RespuestaMensaje:
    inicio = time.monotonic()
    try:
        reply = _limpiar(_pedir_mensaje(p))
        if da_veredicto(reply, FASE_GUARDIA):
            log.warning("Veredicto detectado en %s (%s): %r; se pide otro mensaje", p.sessionId, p.mode, _recortar(reply, 200))
            transcurrido = time.monotonic() - inicio
            if transcurrido > TIEMPO_PARA_REINTENTAR_S:
                return respaldo_guiado(p)
            aviso = (
                "## Corrección\nTu mensaje anterior sonaba a veredicto sobre una opción "
                f"(\"{_recortar(reply, 300)}\"). Escribe otro sin calificar opciones ni el acierto del estudiante: "
                "pregunta solo por el razonamiento."
            )
            reply = _limpiar(_pedir_mensaje(p, aviso, timeout=PLAZO_PLATAFORMA_S - transcurrido))
            if da_veredicto(reply, FASE_GUARDIA):
                log.warning("Veredicto repetido en %s; se usa el mensaje fijo", p.sessionId)
                return respaldo_guiado(p)
    except ErrorModelo as error:
        log.error("Fallo del modelo en %s (%s): %s", p.sessionId, p.mode, error)
        return respaldo_guiado(p)
    return RespuestaMensaje(reply=reply) if reply else respaldo_guiado(p)


# ---------- Revisión ----------

def _entrada_revision(p: PeticionRevision) -> list[dict]:
    q = p.question
    texto_pregunta, imagenes = _contenido_pregunta(q)
    porques = "\n".join(f"{o}. {q.optionRationales[o]}" for o in q.options if q.optionRationales.get(o)) or "(el profesor no escribió el porqué de cada opción)"
    texto = "\n\n".join(filter(None, [
        f"## Pregunta\n{texto_pregunta}",
        f"## Clave del profesor\nRespuesta correcta: {q.correctAnswer}\nExplicación: {q.explanation or '(sin explicación)'}\nPor qué de cada opción:\n{porques}",
        "## Lo que hizo el estudiante\n"
        f"Primera vuelta (solo, como en el examen): {p.firstAnswer or 'sin responder'}\n"
        f"Decisión final (después de razonar con Marco): {p.finalAnswer}\n"
        f"Resultado: {p.outcome}\n"
        f"Usó la Pregunta clave: {'sí' if p.usedKeyQuestion else 'no'}",
        _material(p),
        f"## Perfil del estudiante\n{resumen_perfil(p.student, q.subject, q.component)}",
        f"## Conversación con Marco\n<conversacion>\n{_conversacion(p)}\n</conversacion>",
    ]))
    return [{"type": "input_text", "text": texto}, *imagenes]


def revision(p: PeticionRevision) -> RespuestaRevision:
    try:
        salida = pedir_json(
            instrucciones=ins.INSTRUCCIONES_REVISION,
            contenido=_entrada_revision(p),
            esquema=ins.ESQUEMA_REVISION,
            nombre="revision",
            esfuerzo=ESFUERZO_REVISION,
            max_tokens=2500,
        )
    except ErrorModelo as error:
        log.error("Fallo del modelo en revisión %s: %s", p.sessionId, error)
        return revision_respaldo(p)
    texto = salida["review"].strip()
    return RespuestaRevision(review=texto) if texto else revision_respaldo(p)


# ---------- Rutas ----------

@app.get("/salud")
def salud() -> dict:
    # K_REVISION la pone Cloud Run: sirve para confirmar qué versión está desplegada.
    return {"ok": True, "revision": os.getenv("K_REVISION", "local"), "contrato": 4}


@app.post("/")
def atender(cuerpo: dict, authorization: str | None = Header(default=None)):
    _autorizar(authorization)
    try:
        p = _peticion.validate_python(cuerpo)
    except Exception as error:
        raise HTTPException(status_code=422, detail=f"Petición fuera del contrato v4: {error}") from error
    if p.contractVersion != 4:
        log.warning("Versión de contrato %s; el agente implementa la 4", p.contractVersion)
    if isinstance(p, PeticionRevision):
        return revision(p).model_dump()
    return mensaje_guiado(p).model_dump()
