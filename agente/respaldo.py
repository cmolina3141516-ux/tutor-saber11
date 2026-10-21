"""Mensajes fijos para cuando el modelo falla o su mensaje da un veredicto.

Son los mismos que usa el respaldo de la plataforma (server/tutorLocalAgent.ts), para que el
estudiante no note la diferencia. Igual que allí, no dependen de la respuesta correcta.
"""

from .contrato import PeticionGuia, PeticionRevision, RespuestaGuia, RespuestaRevision


def guia_respaldo(p: PeticionGuia) -> RespuestaGuia:
    necesarias = p.question.requiredDiscards
    descartadas = p.discardedOptions
    if p.phase == "indagacion":
        if not any(m.role == "student" for m in p.history):
            nombre = p.student.firstName.strip()
            saludo = f"Hola, {nombre}. " if nombre else ""
            return RespuestaGuia(
                reply=f"{saludo}Antes de mirar las opciones: ¿qué te está preguntando realmente el enunciado? Dilo con tus palabras.",
                nextPhase="indagacion",
            )
        una = necesarias == 1
        return RespuestaGuia(
            reply=(
                f"Ahora busca {'una opción' if una else f'{necesarias} opciones'} que, según lo que dijiste, "
                f"no {'puede' if una else 'pueden'} ser la respuesta. {'Márcala' if una else 'Márcalas'} con "
                '"Descartar" y explícame qué dato del enunciado te lo indica.'
            ),
            nextPhase="descarte",
        )
    if p.phase == "descarte":
        if len(descartadas) < necesarias:
            reply = (
                "¿Qué opción no encaja con lo que pide el enunciado? Márcala con \"Descartar\" y dime en qué te basas."
                if not descartadas
                else f"Anotado tu descarte de la {descartadas[0]}. ¿Cuál es la siguiente, y qué la contradice?"
            )
            return RespuestaGuia(reply=reply, nextPhase="descarte")
        return RespuestaGuia(
            reply=(
                f"Anotadas tus apuestas: {' y '.join(descartadas)}. Pregunta clave: ¿qué condición tiene que "
                "cumplir sí o sí la respuesta para que responda a TODO lo que pide el enunciado?"
            ),
            nextPhase="pregunta_clave",
        )
    if p.phase == "pregunta_clave":
        return RespuestaGuia(
            reply="Con esa condición en mente, revisa las opciones que te quedan y marca tu decisión final. Después te muestro cómo te fue con cada descarte.",
            nextPhase="decision",
        )
    return RespuestaGuia(reply="Marca tu decisión final cuando lo tengas claro.", nextPhase="decision")


def razon_respaldo(p: PeticionRevision, opcion: str) -> str:
    q = p.question
    if opcion == q.correctAnswer:
        return f"Esta era la correcta. {q.explanation or 'Vuelve a leer qué te llevó a descartarla: ahí está el dato que pasaste por alto.'}"
    return f"Bien descartada: {q.optionRationales.get(opcion) or 'no responde a lo que pide el enunciado.'}"


def revision_respaldo(p: PeticionRevision) -> RespuestaRevision:
    q = p.question
    por_que = q.explanation or "Es la única que cumple todas las condiciones del enunciado."
    if p.finalAnswer == q.correctAnswer:
        conclusion = f"La {q.correctAnswer} es la correcta. {por_que}"
        if p.certainty == "adivine":
            conclusion += " Acertaste, pero dijiste que adivinaste: lee la explicación para que la próxima vez lo sepas."
    else:
        elegida = q.optionRationales.get(p.finalAnswer)
        conclusion = f"La respuesta correcta es la {q.correctAnswer}. {por_que}"
        conclusion += (
            f" Y la {p.finalAnswer}, que elegiste: {elegida}"
            if elegida
            else f" Compárala con la {p.finalAnswer} que elegiste y busca qué condición no cumple esa."
        )
        if p.certainty == "seguro":
            conclusion += " Marcaste que lo sabías: busca qué idea te llevó a esa conclusión, porque ahí está lo que hay que corregir."
    return RespuestaRevision(
        discardReasons={o: razon_respaldo(p, o) for o in p.discardedOptions},
        conclusion=conclusion,
    )
