"""Pruebas del servicio contra el contrato v4 (dos vueltas), sin llamar a OpenAI."""

import base64

import pytest
from fastapi.testclient import TestClient

from agente import imagenes, servicio
from agente.guardia import da_veredicto, quitar_interjeccion
from agente.modelo import ErrorModelo

cliente = TestClient(servicio.app)

PREGUNTA = {
    "subject": "matematicas",
    "competencia": "Formulación y ejecución",
    "component": "Aleatorio",
    "topic": "Probabilidad simple",
    "context": None,
    "text": "En una bolsa hay 3 bolas rojas y 5 azules. ¿Cuál es la probabilidad de sacar una roja?",
    "imageUrl": None,
    "options": ["A", "B", "C", "D"],
    "optionTexts": {"A": "3/5", "B": "3/8", "C": "5/8", "D": "1/3"},
}
ESTUDIANTE = {
    "firstName": "Ana",
    "questionsGuided": 12,
    "questionsCorrect": 9,
    "bySubject": {"matematicas": {"guided": 7, "correct": 5}},
    "byComponent": {"Aleatorio": {"guided": 4, "correct": 3}},
}
APOYO = [{"title": "Probabilidad simple", "text": "Casos favorables sobre casos posibles."}]


def peticion(modo, **extra):
    return {
        "contractVersion": 4,
        "mode": modo,
        "sessionId": "intento_q1",
        "question": PREGUNTA,
        "supportTexts": APOYO,
        "history": [],
        "student": ESTUDIANTE,
        **extra,
    }


def revision(final="A", primera="B", resultado="abandono_correcta"):
    return peticion(
        "review",
        question={
            **PREGUNTA,
            "correctAnswer": "B",
            "explanation": "Hay 3 casos favorables entre 8 posibles.",
            "optionRationales": {"A": "Compara rojas con azules.", "C": "Es la probabilidad de sacar azul."},
        },
        firstAnswer=primera,
        finalAnswer=final,
        outcome=resultado,
        usedKeyQuestion=False,
        history=[{"role": "student", "text": "cambié porque el 8 no aparece", "at": ""}],
    )


@pytest.fixture
def modelo(monkeypatch):
    """Sustituye la llamada a OpenAI por respuestas programadas y guarda lo que recibió."""
    llamadas, respuestas = [], []

    def falso(**kwargs):
        llamadas.append(kwargs)
        r = respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(servicio, "pedir_json", falso)
    return llamadas, respuestas


def test_indicio_sin_respuestas_y_con_material(modelo):
    llamadas, respuestas = modelo
    respuestas.append({"reply": "Si sacas un nombre al azar en tu salón, ¿de qué depende que salgas tú?"})
    r = cliente.post("/", json=peticion("hint"))
    assert r.status_code == 200
    assert r.json() == {"reply": "Si sacas un nombre al azar en tu salón, ¿de qué depende que salgas tú?"}
    entrada = llamadas[0]["contenido"][0]["text"]
    assert "no conoces la respuesta correcta ni la que marcó el estudiante" in entrada
    assert "Respuesta correcta" not in entrada and "Primera vuelta" not in entrada
    assert "Casos favorables sobre casos posibles." in entrada
    assert "Modo: hint" in entrada


def test_guia_indica_respuestas_restantes(modelo):
    llamadas, respuestas = modelo
    respuestas += [{"reply": "¿Qué dato del enunciado usas?"}, {"reply": "Con eso, decide si mantienes o cambias tu respuesta. ¿Qué tiene que cumplir?"}]
    cliente.post("/", json=peticion("guide", studentMessage="es 3 de 8", repliesLeft=1))
    cliente.post("/", json=peticion("guide", studentMessage="la condición es el total", repliesLeft=0))
    assert "Te quedan 1 respuesta(s)" in llamadas[0]["contenido"][0]["text"]
    assert "es tu último mensaje" in llamadas[1]["contenido"][0]["text"]
    assert "<mensaje_estudiante>\nes 3 de 8" in llamadas[0]["contenido"][0]["text"]


def test_pregunta_clave(modelo):
    llamadas, respuestas = modelo
    respuestas.append({"reply": "Pregunta clave: ¿con qué total hay que comparar las rojas?"})
    r = cliente.post("/", json=peticion("key_question"))
    assert r.json()["reply"].startswith("Pregunta clave:")
    assert "Modo: key_question" in llamadas[0]["contenido"][0]["text"]


def test_veredicto_sobre_la_opcion_del_estudiante_se_reemplaza(modelo):
    llamadas, respuestas = modelo
    respuestas += [{"reply": "Vas bien con la B. ¿Por qué?"}, {"reply": "¿Qué dato del enunciado sostiene eso?"}]
    r = cliente.post("/", json=peticion("guide", studentMessage="marqué la B", repliesLeft=1))
    assert r.json()["reply"] == "¿Qué dato del enunciado sostiene eso?"
    assert "Corrección" in llamadas[1]["contenido"][0]["text"]


def test_veredicto_repetido_usa_mensaje_fijo(modelo):
    _, respuestas = modelo
    respuestas += [{"reply": "Esa es la correcta, mantenla."}, {"reply": "¿Seguro que la cambias?"}]
    r = cliente.post("/", json=peticion("guide", studentMessage="la cambio", repliesLeft=1))
    assert r.json()["reply"].startswith("¿En qué dato del enunciado te apoyas")


def test_interjeccion_inicial_se_quita_sin_otra_llamada(modelo):
    llamadas, respuestas = modelo
    respuestas.append({"reply": "Sí, anotado. ¿Qué dato del enunciado lo sostiene?"})
    r = cliente.post("/", json=peticion("guide", studentMessage="puse la B porque son 8", repliesLeft=1))
    assert r.json()["reply"] == "Anotado. ¿Qué dato del enunciado lo sostiene?"
    assert len(llamadas) == 1


def test_fallo_del_modelo_usa_respaldo(modelo):
    _, respuestas = modelo
    respuestas.append(ErrorModelo("timeout"))
    r = cliente.post("/", json=peticion("hint"))
    assert r.status_code == 200
    assert "Probabilidad simple" in r.json()["reply"]


def test_revision_recibe_todo_y_devuelve_review(modelo):
    llamadas, respuestas = modelo
    respuestas.append({"review": "Tenías la B y la cambiaste porque creíste que el 8 no aparecía: sale de 3 + 5."})
    r = cliente.post("/", json=revision())
    assert r.json() == {"review": "Tenías la B y la cambiaste porque creíste que el 8 no aparecía: sale de 3 + 5."}
    entrada = llamadas[0]["contenido"][0]["text"]
    assert "Respuesta correcta: B" in entrada
    assert "Primera vuelta (solo, como en el examen): B" in entrada
    assert "Resultado: abandono_correcta" in entrada


def test_revision_con_fallo_usa_respaldo(modelo):
    _, respuestas = modelo
    respuestas.append(ErrorModelo("caído"))
    r = cliente.post("/", json=revision(final="C", primera=None, resultado="sostuvo_error"))
    assert r.json()["review"].startswith("Hay una idea equivocada")
    assert "La correcta es la B" in r.json()["review"]


def test_llave(monkeypatch, modelo):
    _, respuestas = modelo
    monkeypatch.setattr(servicio, "LLAVE", "secreta")
    assert cliente.post("/", json=peticion("hint")).status_code == 401
    respuestas.append({"reply": "¿Qué te pide?"})
    assert cliente.post("/", json=peticion("hint"), headers={"Authorization": "Bearer secreta"}).status_code == 200


def test_peticion_fuera_de_contrato():
    assert cliente.post("/", json={"mode": "otro"}).status_code == 422
    # Un turno guiado sin mensaje del estudiante no cumple el contrato v4.
    assert cliente.post("/", json={"mode": "guide", "question": PREGUNTA}).status_code == 422


def test_instrucciones_v4():
    from agente.instrucciones import INSTRUCCIONES_GUIA, INSTRUCCIONES_REVISION
    assert "segunda vuelta" in INSTRUCCIONES_GUIA and "mayéutica" in INSTRUCCIONES_GUIA
    assert "descart" not in INSTRUCCIONES_GUIA.lower()
    assert "NUNCA respondas tú la pregunta de tu indicio" in INSTRUCCIONES_GUIA
    assert "abandono_correcta" in INSTRUCCIONES_REVISION


# ---------- Filtro de veredictos ----------

@pytest.mark.parametrize("mensaje", [
    "¡Correcto! Ahora sigue.",
    "La respuesta correcta tiene que ver con el total.",
    "Revisa la B antes de seguir.",
    "¿Estás seguro de esa?",
    "Creo que es la opción C.",
    "Vas por buen camino.",
    "Sí, vas por la idea: ahora compara.",
    "Vas contando bien qué dato usaste.",
    "No, fíjate en el total.",
])
def test_guardia_detecta(mensaje):
    assert da_veredicto(mensaje, "segunda_vuelta")


@pytest.mark.parametrize("mensaje", [
    "¿Qué dato del enunciado contradice esa idea?",
    "Citaste la tabla. ¿Qué parte de ella sostiene lo que dices?",
    "¿Qué condición tiene que cumplir la respuesta?",
    "No te la voy a decir de una, pero te acompaño para que la saques tú.",
])
def test_guardia_deja_pasar(mensaje):
    assert not da_veredicto(mensaje, "segunda_vuelta")


def test_quitar_interjeccion():
    assert quitar_interjeccion("Exacto. ¿Y el total?") == "¿Y el total?"
    assert quitar_interjeccion("¿Qué dato usas?") == "¿Qué dato usas?"


# ---------- Imágenes del banco ----------

SVG = '<svg xmlns="http://www.w3.org/2000/svg"><text x="1" y="1">Desempleo (%)</text><text>15,9</text><text>2020</text></svg>'
SVG_URL = "data:image/svg+xml;base64," + base64.b64encode(SVG.encode()).decode()


def test_svg_se_convierte_a_png(monkeypatch):
    monkeypatch.setattr(imagenes, "_svg_a_png", lambda svg: b"PNG")
    assert imagenes.partes_imagen(SVG_URL, "img") == [{"type": "input_image", "image_url": "data:image/png;base64,UE5H", "detail": "auto"}]


def test_svg_sin_conversion_manda_su_texto(monkeypatch):
    def falla(svg):
        raise OSError("sin libcairo")
    monkeypatch.setattr(imagenes, "_svg_a_png", falla)
    partes = imagenes.partes_imagen(SVG_URL, "la imagen del enunciado")
    assert partes[0]["type"] == "input_text" and "Desempleo (%) | 15,9 | 2020" in partes[0]["text"]


def test_imagen_normal_pasa_tal_cual():
    assert imagenes.partes_imagen("https://x/y.png", "img")[0]["image_url"] == "https://x/y.png"


def test_revision_no_inventa_razonamientos():
    from agente.instrucciones import INSTRUCCIONES_REVISION
    assert "NO inventes lo que pensó" in INSTRUCCIONES_REVISION


# ---------- Informe de la prueba corta (contrato v5) ----------

def pregunta_informe(n, tema, acerto, marco="A", correcta="B", **extra):
    return {
        "n": n, "competencia": "Formulación y ejecución", "component": "Aleatorio", "topic": tema,
        "difficulty": "media", "text": f"Enunciado {n}", "optionTexts": {"A": "uno", "B": "dos", "C": "tres", "D": "cuatro"},
        "answer": correcta if acerto else marco, "correctAnswer": correcta, "isCorrect": acerto,
        "explanation": f"Explicación {n}", "chosenRationale": None if acerto else f"Por qué no {n}", "timeSec": 40, **extra,
    }


def informe(**extra):
    preguntas = [pregunta_informe(1, "Probabilidad condicional", False), pregunta_informe(2, "Probabilidad condicional", False),
                 pregunta_informe(3, "Medidas de tendencia central", True), pregunta_informe(4, "Medidas de tendencia central", True)]
    return {
        "contractVersion": 5, "mode": "quiz_report", "sessionId": "intento1",
        "quiz": {"title": "Prueba corta Aleatorio 1", "subject": "matematicas", "trainingTitle": "Aleatorio 1"},
        "student": ESTUDIANTE, "score": 2, "total": 4, "evaluative": True, "questions": preguntas,
        "supportTopics": [{"topic": "Probabilidad condicional", "titles": ["Tablas de contingencia"]}], **extra,
    }


def test_informe_recibe_preguntas_claves_y_material(modelo):
    llamadas, respuestas = modelo
    respuestas.append({
        "summary": "Ana, dominas las medidas de tendencia central.", "strengths": ["Promedio y mediana."],
        "improve": [{"topic": "Probabilidad condicional", "diagnosis": "Usaste el total general.", "advice": "Ubica la condición."}],
        "nextSteps": ["Mira \"Tablas de contingencia\"."],
    })
    r = cliente.post("/", json=informe())
    assert r.status_code == 200
    assert r.json()["report"]["improve"][0]["topic"] == "Probabilidad condicional"
    entrada = llamadas[0]["contenido"][0]["text"]
    assert "### Pregunta 1 — FALLÓ" in entrada and "### Pregunta 3 — ACERTÓ" in entrada
    assert "Marcó: A · Correcta: B" in entrada and "Por qué no la A: Por qué no 1" in entrada
    assert '"Tablas de contingencia"' in entrada and 'Entrenamiento pareado: "Aleatorio 1"' in entrada
    assert llamadas[0]["nombre"] == "informe_prueba"


def test_informe_recorta_listas_largas(modelo):
    _, respuestas = modelo
    respuestas.append({"summary": "Bien.", "strengths": ["a", "b", "c", "d"], "improve": [], "nextSteps": ["1", "2", "3", "4", " "]})
    rep = cliente.post("/", json=informe()).json()["report"]
    assert rep["strengths"] == ["a", "b", "c"] and rep["nextSteps"] == ["1", "2", "3"]


def test_informe_respaldo_si_falla_el_modelo(modelo):
    _, respuestas = modelo
    respuestas.append(ErrorModelo("timeout"))
    rep = cliente.post("/", json=informe()).json()["report"]
    assert rep["summary"].startswith("Ana, acertaste 2 de 4")
    assert rep["improve"][0]["topic"] == "Probabilidad condicional"
    assert "Tablas de contingencia" in rep["improve"][0]["advice"]
    assert rep["strengths"] == ["Respondiste bien las 2 preguntas de Medidas de tendencia central."]
    assert any("Aleatorio 1" in paso for paso in rep["nextSteps"])


def test_salud_contrato_5():
    assert cliente.get("/salud").json()["contrato"] == 5
