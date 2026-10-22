"""Mensajes fijos para cuando el modelo falla o su mensaje da un veredicto.

Son los mismos que usa el respaldo de la plataforma (server/tutorLocalAgent.ts), para que el
estudiante no note la diferencia. Igual que allí, antes de la revisión no dependen de la respuesta
correcta ni de la primera respuesta del estudiante.
"""

from .contrato import (
    InformePrueba,
    PeticionGuia,
    PeticionIndicio,
    PeticionInformePrueba,
    PeticionPreguntaClave,
    PeticionRevision,
    PuntoAMejorar,
    RespuestaInformePrueba,
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


def informe_respaldo(p: PeticionInformePrueba) -> RespuestaInformePrueba:
    """Informe sin IA, armado con las cifras de la prueba (igual que server/tutorLocalAgent.ts)."""
    por_tema: dict[str, list[bool]] = {}
    for q in p.questions:
        por_tema.setdefault(q.topic or q.component or "Otros temas", []).append(q.isCorrect)
    material = {m.topic: m.titles for m in p.supportTopics}
    nombre = f"{p.student.firstName.strip()}, " if p.student.firstName.strip() else ""

    fortalezas = [f"Respondiste bien las {len(r)} preguntas de {tema}." for tema, r in por_tema.items() if len(r) >= 2 and all(r)][:3]
    fallos = sorted(((r.count(False), tema, len(r)) for tema, r in por_tema.items() if not all(r)), reverse=True)[:3]
    mejorar = []
    for errores, tema, n in fallos:
        titulos = material.get(tema, [])
        consejo = f"Revisa el material de apoyo \"{titulos[0]}\" y la explicación de cada pregunta." if titulos else "Lee con calma la explicación de cada pregunta que fallaste y vuelve a resolverla sin mirar la respuesta."
        mejorar.append(PuntoAMejorar(topic=tema, diagnosis=f"Fallaste {errores} de {n} pregunta(s) de este tema.", advice=consejo))

    pasos = []
    if mejorar:
        pasos.append(f"Empieza por {mejorar[0].topic}: repasa las preguntas que fallaste y su explicación.")
    if p.quiz.trainingTitle and mejorar:
        pasos.append(f"Repite la segunda vuelta del entrenamiento \"{p.quiz.trainingTitle}\" razonando con Marco.")
    pasos.append("En la próxima prueba, subraya qué pide exactamente el enunciado antes de mirar las opciones.")

    if p.score == p.total:
        resumen = f"{nombre}respondiste bien las {p.total} preguntas. Mantén el ritmo y busca preguntas de mayor dificultad."
    elif p.score * 2 >= p.total:
        resumen = f"{nombre}acertaste {p.score} de {p.total} preguntas. Hay una base sólida; enfócate en los temas donde fallaste."
    else:
        resumen = f"{nombre}acertaste {p.score} de {p.total} preguntas. Vale la pena repasar los temas de esta prueba antes de seguir."
    return RespuestaInformePrueba(report=InformePrueba(summary=resumen, strengths=fortalezas, improve=mejorar, nextSteps=pasos[:3]))
