"""Tipos del contrato v3 entre la plataforma Prueba Saber 11 y Marco.

Son el espejo en Python de src/tutor/contract.ts (en el repositorio de la plataforma) y de
docs/tutor-agent-contract.md. Si la plataforma cambia el contrato, se cambia aquí.

Se aceptan campos extra para que una versión nueva de la plataforma no rompa al agente.
"""

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

Opcion = Literal["A", "B", "C", "D"]
Fase = Literal["indagacion", "descarte", "pregunta_clave", "decision", "revision"]
Certeza = Literal["seguro", "dudas", "adivine"]

# Fases en las que el estudiante conversa con Marco, y a cuál pasa cada una.
SIGUIENTE_FASE: dict[str, Fase] = {
    "indagacion": "descarte",
    "descarte": "pregunta_clave",
    "pregunta_clave": "decision",
}


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
    requiredDiscards: int = 2


class PreguntaConClave(Pregunta):
    correctAnswer: Opcion
    explanation: str = ""
    optionRationales: dict[Opcion, str] = Field(default_factory=dict)


class Mensaje(Flexible):
    role: Literal["student", "tutor"]
    text: str
    at: str = ""


class Contadores(Flexible):
    guided: int = 0
    correct: int = 0
    discardsTotal: int = 0
    discardsGood: int = 0


class Estudiante(Flexible):
    firstName: str = ""
    questionsGuided: int = 0
    questionsCorrect: int = 0
    discardsTotal: int = 0
    discardsGood: int = 0
    bySubject: dict[str, Contadores] = Field(default_factory=dict)
    byComponent: dict[str, Contadores] = Field(default_factory=dict)


class PeticionGuia(Flexible):
    contractVersion: int = 3
    mode: Literal["guide"]
    sessionId: str = ""
    question: Pregunta
    phase: Fase
    discardedOptions: list[Opcion] = Field(default_factory=list)
    history: list[Mensaje] = Field(default_factory=list)
    studentMessage: str
    student: Estudiante = Field(default_factory=Estudiante)


class PeticionRevision(Flexible):
    contractVersion: int = 3
    mode: Literal["review"]
    sessionId: str = ""
    question: PreguntaConClave
    discardedOptions: list[Opcion] = Field(default_factory=list)
    finalAnswer: Opcion
    certainty: Certeza = "dudas"
    history: list[Mensaje] = Field(default_factory=list)
    student: Estudiante = Field(default_factory=Estudiante)


Peticion = Annotated[Union[PeticionGuia, PeticionRevision], Field(discriminator="mode")]


class RespuestaGuia(BaseModel):
    reply: str
    nextPhase: Fase


class RespuestaRevision(BaseModel):
    discardReasons: dict[Opcion, str]
    conclusion: str
