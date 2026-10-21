"""Convierte el progreso del estudiante en una nota corta para Marco.

El modelo no necesita las cifras crudas: necesita saber en qué nivel está el estudiante en esta
área y este componente, para ajustar cuánto andamiaje darle. La nota se calcula aquí y no en el
prompt, para que sea siempre la misma regla y gaste pocos tokens.
"""

from .contrato import Contadores, Estudiante

# Con menos preguntas repasadas que esto, los porcentajes todavía no dicen nada.
MINIMO_PARA_JUZGAR = 4


def _porcentaje(parte: int, total: int) -> int:
    return round(100 * parte / total) if total else 0


def _nivel(c: Contadores) -> str:
    if c.guided < MINIMO_PARA_JUZGAR:
        return "sin datos suficientes"
    # Aciertos en la decisión final de la segunda vuelta.
    aciertos = c.correct / c.guided
    if aciertos >= 0.75:
        return "fuerte"
    if aciertos < 0.45:
        return "necesita apoyo"
    return "en progreso"


def _linea(etiqueta: str, c: Contadores) -> str:
    if c.guided == 0:
        return f"- {etiqueta}: primera vez que trabaja aquí con Marco."
    return (
        f"- {etiqueta}: {c.guided} preguntas repasadas con Marco, {_porcentaje(c.correct, c.guided)} % "
        f"acertadas en la decisión final. Nivel: {_nivel(c)}."
    )


def resumen_perfil(estudiante: Estudiante, area: str, componente: str | None) -> str:
    nombre = estudiante.firstName.strip() or "el estudiante"
    general = Contadores(guided=estudiante.questionsGuided, correct=estudiante.questionsCorrect)
    lineas = [f"Nombre: {nombre}.", _linea("En general", general)]
    lineas.append(_linea(f"En esta área ({area})", estudiante.bySubject.get(area, Contadores())))
    if componente:
        lineas.append(_linea(f"En este componente ({componente})", estudiante.byComponent.get(componente, Contadores())))
    return "\n".join(lineas)
