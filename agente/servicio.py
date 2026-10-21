"""Servicio HTTP de Marco (contrato v3).

La plataforma hace POST a la raíz con un turno guiado (mode "guide") o una revisión
(mode "review") y espera el JSON del contrato en menos de 20 s.
"""

import hmac
import logging
import os
import time

from fastapi import FastAPI, Header, HTTPException
from pydantic import TypeAdapter

from . import instrucciones as ins
from .contrato import (
    SIGUIENTE_FASE,
    Peticion,
    PeticionGuia,
    PeticionRevision,
    Pregunta,
    RespuestaGuia,
    RespuestaRevision,
)
from .guardia import da_veredicto
from .modelo import ESFUERZO_GUIA, ESFUERZO_REVISION, ErrorModelo, pedir_json
from .perfil import resumen_perfil
from .respaldo import guia_respaldo, razon_respaldo, revision_respaldo

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
            imagenes.append({"type": "input_image", "image_url": q.context.imageUrl, "detail": "auto"})
            partes.append("(La imagen del contexto va adjunta.)")
    partes.append(f"\nEnunciado:\n{q.text or '(el enunciado está en la imagen adjunta)'}")
    if q.imageUrl:
        imagenes.append({"type": "input_image", "image_url": q.imageUrl, "detail": "auto"})
        partes.append("(La imagen del enunciado va adjunta.)")
    partes.append("\nOpciones:")
    partes += [f"{o}. {q.optionTexts.get(o, '(ver imagen)')}" for o in q.options]
    return "\n".join(partes), imagenes


def _conversacion(p: PeticionGuia | PeticionRevision) -> str:
    recientes = p.history[-MAX_HISTORIAL:]
    if not recientes:
        return "(todavía no hay conversación)"
    quien = {"student": "Estudiante", "tutor": "Marco"}
    return "\n".join(f"{quien[m.role]}: {_recortar(m.text)}" for m in recientes)


# ---------- Turno guiado ----------

def _estado_guia(p: PeticionGuia) -> str:
    necesarias = p.question.requiredDiscards
    descartadas = ", ".join(p.discardedOptions) or "ninguna"
    turnos = sum(1 for m in p.history if m.role == "student")
    lineas = [
        f"Fase actual: {p.phase}",
        f"Turnos del estudiante en esta pregunta (sin contar este): {turnos}",
        f"Descartes marcados con el botón: {descartadas} ({len(p.discardedOptions)} de {necesarias} requeridos)",
    ]
    if p.phase == "descarte" and len(p.discardedOptions) < necesarias:
        lineas.append("Todavía NO puedes avanzar: faltan descartes por marcar.")
    return "\n".join(lineas)


def _entrada_guia(p: PeticionGuia, aviso: str = "") -> list[dict]:
    texto_pregunta, imagenes = _contenido_pregunta(p.question)
    texto = "\n\n".join(filter(None, [
        f"## Pregunta (no conoces la respuesta correcta)\n{texto_pregunta}",
        f"## Perfil del estudiante\n{resumen_perfil(p.student, p.question.subject, p.question.component)}",
        f"## Estado\n{_estado_guia(p)}",
        f"## Conversación hasta ahora\n<conversacion>\n{_conversacion(p)}\n</conversacion>",
        f"## Mensaje nuevo del estudiante\n<mensaje_estudiante>\n{_recortar(p.studentMessage, 1500)}\n</mensaje_estudiante>",
        aviso,
    ]))
    return [{"type": "input_text", "text": texto}, *imagenes]


def _pedir_guia(p: PeticionGuia, aviso: str = "", timeout: float | None = None) -> dict:
    return pedir_json(
        instrucciones=ins.INSTRUCCIONES_GUIA,
        contenido=_entrada_guia(p, aviso),
        esquema=ins.ESQUEMA_GUIA,
        nombre="turno_guiado",
        esfuerzo=ESFUERZO_GUIA,
        max_tokens=1500,
        timeout=timeout,
    )


def turno_guiado(p: PeticionGuia) -> RespuestaGuia:
    if p.phase not in SIGUIENTE_FASE:
        # En decisión o revisión la plataforma no debería consultar al agente.
        return guia_respaldo(p)

    inicio = time.monotonic()
    try:
        salida = _pedir_guia(p)
        if da_veredicto(salida["reply"]):
            log.warning("Veredicto detectado en %s (fase %s); se pide otro mensaje", p.sessionId, p.phase)
            transcurrido = time.monotonic() - inicio
            if transcurrido > TIEMPO_PARA_REINTENTAR_S:
                return guia_respaldo(p)
            restante = PLAZO_PLATAFORMA_S - transcurrido
            aviso = (
                "## Corrección\nTu mensaje anterior sonaba a veredicto sobre una opción o un descarte "
                f"(\"{_recortar(salida['reply'], 300)}\"). Escribe otro sin calificar opciones ni descartes: "
                "pregunta solo por el razonamiento."
            )
            salida = _pedir_guia(p, aviso, timeout=restante)
            if da_veredicto(salida["reply"]):
                log.warning("Veredicto repetido en %s; se usa el mensaje fijo", p.sessionId)
                return guia_respaldo(p)
    except ErrorModelo as error:
        log.error("Fallo del modelo en turno guiado %s: %s", p.sessionId, error)
        return guia_respaldo(p)

    reply = salida["reply"].strip()
    if not reply:
        return guia_respaldo(p)
    avanzar = bool(salida["avanzar"])
    if p.phase == "descarte" and len(p.discardedOptions) < p.question.requiredDiscards and avanzar:
        # El mensaje ya planteaba la pregunta clave, pero faltan descartes: mejor el mensaje fijo.
        return guia_respaldo(p)
    return RespuestaGuia(reply=reply, nextPhase=SIGUIENTE_FASE[p.phase] if avanzar else p.phase)


# ---------- Revisión ----------

def _entrada_revision(p: PeticionRevision) -> list[dict]:
    q = p.question
    texto_pregunta, imagenes = _contenido_pregunta(q)
    porques = "\n".join(f"{o}. {q.optionRationales[o]}" for o in q.options if q.optionRationales.get(o)) or "(el profesor no escribió el porqué de cada opción)"
    descartes = "\n".join(
        f"- {o}: {'era la CORRECTA (mal descartada)' if o == q.correctAnswer else 'BIEN descartada'}"
        for o in p.discardedOptions
    ) or "- (no descartó ninguna opción)"
    resultado = "acertó" if p.finalAnswer == q.correctAnswer else "falló"
    texto = "\n\n".join([
        f"## Pregunta\n{texto_pregunta}",
        f"## Clave del profesor\nRespuesta correcta: {q.correctAnswer}\nExplicación: {q.explanation or '(sin explicación)'}\nPor qué de cada opción:\n{porques}",
        f"## Lo que hizo el estudiante\nDescartes (calculados por la plataforma):\n{descartes}\nDecisión final: {p.finalAnswer} ({resultado})\nCerteza que marcó: {p.certainty}",
        f"## Perfil del estudiante\n{resumen_perfil(p.student, q.subject, q.component)}",
        f"## Conversación con Marco\n<conversacion>\n{_conversacion(p)}\n</conversacion>",
    ])
    return [{"type": "input_text", "text": texto}, *imagenes]


def revision(p: PeticionRevision) -> RespuestaRevision:
    try:
        salida = pedir_json(
            instrucciones=ins.INSTRUCCIONES_REVISION,
            contenido=_entrada_revision(p),
            esquema=ins.ESQUEMA_REVISION,
            nombre="revision",
            esfuerzo=ESFUERZO_REVISION,
            max_tokens=3000,
        )
    except ErrorModelo as error:
        log.error("Fallo del modelo en revisión %s: %s", p.sessionId, error)
        return revision_respaldo(p)

    escritas = {r["opcion"]: r["texto"].strip() for r in salida["razones"] if r["texto"].strip()}
    # Una razón por cada descarte, ni más ni menos; si el modelo omitió alguna, se usa la del profesor.
    razones = {o: escritas.get(o) or razon_respaldo(p, o) for o in p.discardedOptions}
    conclusion = salida["conclusion"].strip() or revision_respaldo(p).conclusion
    return RespuestaRevision(discardReasons=razones, conclusion=conclusion)


# ---------- Rutas ----------

@app.get("/salud")
def salud() -> dict:
    # K_REVISION la pone Cloud Run: sirve para confirmar qué versión está desplegada.
    return {"ok": True, "revision": os.getenv("K_REVISION", "local")}


@app.post("/")
def atender(cuerpo: dict, authorization: str | None = Header(default=None)):
    _autorizar(authorization)
    try:
        p = _peticion.validate_python(cuerpo)
    except Exception as error:
        raise HTTPException(status_code=422, detail=f"Petición fuera del contrato v3: {error}") from error
    if p.contractVersion != 3:
        log.warning("Versión de contrato %s; el agente implementa la 3", p.contractVersion)
    if isinstance(p, PeticionGuia):
        return turno_guiado(p).model_dump()
    return revision(p).model_dump()
