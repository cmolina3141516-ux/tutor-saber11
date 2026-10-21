"""Mensajes fijos para cuando el modelo falla o su mensaje da un veredicto.

Son los mismos que usa el respaldo de la plataforma (server/tutorLocalAgent.ts), para que el
estudiante no note la diferencia. Igual que allí, antes de la revisión no dependen de la respuesta
correcta ni de la primera respuesta del estudiante.
"""

from .contrato import (
    PeticionGuia,
    PeticionIndicio,
    PeticionPreguntaClave,
    PeticionRevision,
    RespuestaMensaje,
    RespuestaRevision,
)

CONSEJO = {
    "mantuvo_correcta": "La tenías bien y la sostuviste: lo sabes.",
    "corrigio": "La corregiste razonando con Marco. Repásalo pronto para que se quede.",
    "abandono_correcta": "Tenías la correcta y la cambiaste. Revisa qué te hizo dudar.",
    "sostuvo_error": "Hay una idea equivocada que conviene corregir primero.",
}


def _tema(p) -> str:
    return p.question.topic or p.question.component or "el tema de la pregunta"


def indicio_respaldo(p: PeticionIndicio) -> RespuestaMensaje:
    nombre = f"{p.student.firstName.strip()}, " if p.student.firstName.strip() else ""
    return RespuestaMensaje(
        reply=f"{nombre}antes de decidir si mantienes tu respuesta, piensa en la idea que hay detrás: esta pregunta es de {_tema(p)}. ¿Qué tendría que cumplir una respuesta para ser la correcta?"
    )


def guia_respaldo(p: PeticionGuia) -> RespuestaMensaje:
    if p.repliesLeft > 0:
        return RespuestaMensaje(reply="¿En qué dato del enunciado te apoyas para decir eso? Señálalo y explícame qué te dice.")
    return RespuestaMensaje(reply="Con lo que has pensado, revisa otra vez tu respuesta y decide si la mantienes o la cambias.")


def pregunta_clave_respaldo(_p: PeticionPreguntaClave) -> RespuestaMensaje:
    return RespuestaMensaje(
        reply="Pregunta clave: ¿qué condición tiene que cumplir sí o sí la respuesta para responder a TODO lo que pide el enunciado? Compara cada opción con esa condición."
    )


def revision_respaldo(p: PeticionRevision) -> RespuestaRevision:
    q = p.question
    por_que = q.explanation or "Es la única que cumple todas las condiciones del enunciado."
    return RespuestaRevision(review=f"{CONSEJO[p.outcome]} La correcta es la {q.correctAnswer}: {por_que}")


def respaldo_guiado(p) -> RespuestaMensaje:
    if isinstance(p, PeticionIndicio):
        return indicio_respaldo(p)
    if isinstance(p, PeticionGuia):
        return guia_respaldo(p)
    return pregunta_clave_respaldo(p)
