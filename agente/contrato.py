"""Tipos del contrato v4 entre la plataforma Prueba Saber 11 y Marco (entrenamiento en dos vueltas).

Son el espejo en Python de src/tutor/contract.ts (en el repositorio de la plataforma) y de
docs/tutor-agent-contract.md. Si la plataforma cambia el contrato, se cambia aquí.

Se aceptan campos extra para que una versión nueva de la plataforma no rompa al agente.
"""

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

Opcion = Literal["A", "B", "C", "D"]
Resultado = Literal["mantuvo_correcta", "corrigio", "abandono_correcta", "sostuvo_error"]


class Flexible(BaseModel):
    model_config = ConfigDict(extra="allow")


class Contexto(Flexible):
    title: str = ""
    text: str = ""
    imageUrl: Optional[str] = None


class Pregunta(Flexible):
    subject: str
    competencia: str = ""
    component: Optional[str] = None
    topic: Optional[str] = None
    context: Optional[Contexto] = None
    text: Optional[str] = None
    imageUrl: Optional[str] = None
    options: list[Opcion]
    optionTexts: dict[Opcion, str] = Field(default_factory=dict)


class PreguntaConClave(Pregunta):
    correctAnswer: Opcion
    explanation: str = ""
    optionRationales: dict[Opcion, str] = Field(default_factory=dict)


class Mensaje(Flexible):
    role: Literal["student", "tutor"]
    text: str
    at: str = ""


class TextoApoyo(Flexible):
    title: str = ""
    text: str = ""


class Contadores(Flexible):
    guided: int = 0
    correct: int = 0


class Estudiante(Flexible):
    firstName: str = ""
    questionsGuided: int = 0
    questionsCorrect: int = 0
    bySubject: dict[str, Contadores] = Field(default_factory=dict)
    byComponent: dict[str, Contadores] = Field(default_factory=dict)


class Base(Flexible):
    contractVersion: int = 4
    sessionId: str = ""
    supportTexts: list[TextoApoyo] = Field(default_factory=list)
    history: list[Mensaje] = Field(default_factory=list)
    student: Estudiante = Field(default_factory=Estudiante)


# Sin respuesta correcta ni respuesta de la primera vuelta.
class PeticionIndicio(Base):
    mode: Literal["hint"]
    question: Pregunta


class PeticionGuia(Base):
    mode: Literal["guide"]
    question: Pregunta
    studentMessage: str
    # Respuestas que le quedan a Marco en esta pregunta después de esta (0 = la última).
    repliesLeft: int = 0


class PeticionPreguntaClave(Base):
    mode: Literal["key_question"]
    question: Pregunta


# Después de la decisión final: ya viajan la correcta y las dos respuestas.
class PeticionRevision(Base):
    mode: Literal["review"]
    question: PreguntaConClave
    firstAnswer: Optional[Opcion] = None
    finalAnswer: Opcion
    outcome: Resultado
    usedKeyQuestion: bool = False


PeticionGuiada = Union[PeticionIndicio, PeticionGuia, PeticionPreguntaClave]
Peticion = Annotated[Union[PeticionIndicio, PeticionGuia, PeticionPreguntaClave, PeticionRevision], Field(discriminator="mode")]


class RespuestaMensaje(BaseModel):
    reply: str


class RespuestaRevision(BaseModel):
    review: str
