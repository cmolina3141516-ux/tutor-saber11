"""Pruebas del servicio contra el contrato v3, sin llamar a OpenAI."""

import pytest
from fastapi.testclient import TestClient

from agente import servicio
from agente.guardia import da_veredicto
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
    "requiredDiscards": 2,
}
ESTUDIANTE = {
    "firstName": "Ana",
    "questionsGuided": 12,
    "questionsCorrect": 9,
    "discardsTotal": 24,
    "discardsGood": 21,
    "bySubject": {"matematicas": {"guided": 7, "correct": 5, "discardsTotal": 14, "discardsGood": 12}},
    "byComponent": {"Aleatorio": {"guided": 4, "correct": 3, "discardsTotal": 8, "discardsGood": 7}},
}


def guia(fase="indagacion", descartes=(), mensaje="Pide la probabilidad de sacar roja", historial=()):
    return {
        "contractVersion": 3,
        "mode": "guide",
        "sessionId": "uid_intento_q1",
        "question": PREGUNTA,
        "phase": fase,
        "discardedOptions": list(descartes),
        "history": list(historial),
        "studentMessage": mensaje,
        "student": ESTUDIANTE,
    }


def revision(descartes=("A", "C"), final="D", certeza="seguro"):
    return {
        "contractVersion": 3,
        "mode": "review",
        "sessionId": "uid_intento_q1",
        "question": {
            **PREGUNTA,
            "correctAnswer": "B",
            "explanation": "Hay 3 casos favorables entre 8 posibles.",
            "optionRationales": {"A": "Compara rojas con azules.", "C": "Es la probabilidad de sacar azul."},
        },
        "discardedOptions": list(descartes),
        "finalAnswer": final,
        "certainty": certeza,
        "history": [{"role": "student", "text": "Descarto A porque compara", "at": "2026-10-20T15:00:00Z"}],
        "student": ESTUDIANTE,
    }


@pytest.fixture
def modelo(monkeypatch):
    """Sustituye la llamada a OpenAI por respuestas programadas y guarda lo que recibió."""
    llamadas = []
    respuestas = []

    def falso(**kwargs):
        llamadas.append(kwargs)
        r = respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(servicio, "pedir_json", falso)
    return llamadas, respuestas


def test_turno_guiado_sin_respuesta_correcta(modelo):
    llamadas, respuestas = modelo
    respuestas.append({"reply": "¿Qué dato del enunciado te dice cuántas bolas hay en total?", "avanzar": False})
    r = cliente.post("/", json=guia())
    assert r.status_code == 200
    assert r.json() == {"reply": "¿Qué dato del enunciado te dice cuántas bolas hay en total?", "nextPhase": "indagacion"}
    entrada = llamadas[0]["contenido"][0]["text"]
    assert "no conoces la respuesta correcta" in entrada
    assert "Respuesta correcta" not in entrada
    assert "Nivel:" in entrada


def test_avanza_un_solo_paso(modelo):
    _, respuestas = modelo
    respuestas.append({"reply": "Ahora descarta dos opciones con el botón y dime qué dato lo justifica.", "avanzar": True})
    r = cliente.post("/", json=guia())
    assert r.json()["nextPhase"] == "descarte"


def test_no_sale_de_descarte_sin_los_descartes(modelo):
    _, respuestas = modelo
    respuestas.append({"reply": "Pregunta clave: ¿qué condición debe cumplir?", "avanzar": True})
    r = cliente.post("/", json=guia("descarte", ["A"], "Descarto la A"))
    assert r.json()["nextPhase"] == "descarte"
    assert "siguiente" in r.json()["reply"]


def test_veredicto_se_reemplaza(modelo):
    llamadas, respuestas = modelo
    respuestas.append({"reply": "¡Bien descartada! Ahora mira la B.", "avanzar": False})
    respuestas.append({"reply": "¿Qué dato del enunciado contradice la opción A?", "avanzar": False})
    r = cliente.post("/", json=guia("descarte", ["A"], "Descarto la A porque compara rojas con azules"))
    assert r.json()["reply"] == "¿Qué dato del enunciado contradice la opción A?"
    assert "Corrección" in llamadas[1]["contenido"][0]["text"]


def test_veredicto_repetido_usa_mensaje_fijo(modelo):
    _, respuestas = modelo
    respuestas += [{"reply": "Correcto, esa no era.", "avanzar": False}, {"reply": "¿Seguro que la A no?", "avanzar": False}]
    r = cliente.post("/", json=guia("descarte", ["A"], "Descarto la A"))
    assert r.json() == {"reply": "Anotado tu descarte de la A. ¿Cuál es la siguiente, y qué la contradice?", "nextPhase": "descarte"}


def test_fallo_del_modelo_no_deja_sin_respuesta(modelo):
    _, respuestas = modelo
    respuestas.append(ErrorModelo("timeout"))
    r = cliente.post("/", json=guia("pregunta_clave", ["A", "C"], "Debe ser casos favorables sobre el total"))
    assert r.status_code == 200
    assert r.json()["nextPhase"] == "decision"


def test_revision_una_razon_por_descarte(modelo):
    llamadas, respuestas = modelo
    respuestas.append({
        "razones": [{"opcion": "A", "texto": "Bien descartada: compara rojas con azules, no con el total."}, {"opcion": "D", "texto": "sobra"}],
        "conclusion": "La B es la correcta porque hay 3 rojas entre 8 bolas.",
    })
    r = cliente.post("/", json=revision())
    cuerpo = r.json()
    assert set(cuerpo["discardReasons"]) == {"A", "C"}
    assert cuerpo["discardReasons"]["A"].startswith("Bien descartada")
    assert cuerpo["discardReasons"]["C"] == "Bien descartada: Es la probabilidad de sacar azul."
    entrada = llamadas[0]["contenido"][0]["text"]
    assert "Respuesta correcta: B" in entrada and "Certeza que marcó: seguro" in entrada


def test_revision_marca_el_descarte_de_la_correcta(modelo):
    llamadas, respuestas = modelo
    respuestas.append(ErrorModelo("caído"))
    r = cliente.post("/", json=revision(descartes=("B", "C"), final="A"))
    assert r.json()["discardReasons"]["B"].startswith("Esta era la correcta.")
    assert "Marcaste que lo sabías" in r.json()["conclusion"]


def test_llave(monkeypatch, modelo):
    _, respuestas = modelo
    monkeypatch.setattr(servicio, "LLAVE", "secreta")
    assert cliente.post("/", json=guia()).status_code == 401
    respuestas.append({"reply": "¿Qué te pide?", "avanzar": False})
    assert cliente.post("/", json=guia(), headers={"Authorization": "Bearer secreta"}).status_code == 200


def test_peticion_fuera_de_contrato():
    assert cliente.post("/", json={"mode": "otro"}).status_code == 422


@pytest.mark.parametrize("mensaje", [
    "¡Correcto! Ahora sigue.",
    "Bien descartada.",
    "La respuesta correcta tiene que ver con el total.",
    "Revisa la B antes de seguir.",
    "¿Estás seguro de esa?",
    "Creo que es la opción C.",
    "Vas por buen camino.",
    # Frases que el modelo real produjo en la primera prueba (2026-10-21).
    "Sí, vas por la idea: ahora compara.",
    "Vas sumando con el descarte.",
    "No, fíjate en el total.",
    "Sí, va por esa idea: ahora descarta.",
    "Vas contando bien qué dato usaste.",
])
def test_guardia_detecta(mensaje):
    assert da_veredicto(mensaje)


@pytest.mark.parametrize("mensaje", [
    "¿Qué dato del enunciado contradice la opción A?",
    "Citaste la tabla. ¿Qué parte de ella sostiene ese descarte?",
    "Lo que se pide es a cuánto equivale la parte roja. ¿Cuántas bolas hay en total?",
    "¿Qué condición tiene que cumplir la respuesta?",
    "No te la voy a decir de una, pero te acompaño para que la saques tú.",
])
def test_guardia_deja_pasar(mensaje):
    assert not da_veredicto(mensaje)


# ---------- Imágenes del banco ----------

from agente import imagenes

SVG = '<svg xmlns="http://www.w3.org/2000/svg"><text x="1" y="1">Desempleo (%)</text><text>15,9</text><text>2020</text></svg>'
SVG_URL = "data:image/svg+xml;base64," + __import__("base64").b64encode(SVG.encode()).decode()


def test_svg_se_convierte_a_png(monkeypatch):
    monkeypatch.setattr(imagenes, "_svg_a_png", lambda svg: b"PNG")
    partes = imagenes.partes_imagen(SVG_URL, "la imagen del enunciado")
    assert partes == [{"type": "input_image", "image_url": "data:image/png;base64,UE5H", "detail": "auto"}]


def test_svg_sin_conversion_manda_su_texto(monkeypatch):
    def falla(svg):
        raise OSError("sin libcairo")
    monkeypatch.setattr(imagenes, "_svg_a_png", falla)
    partes = imagenes.partes_imagen(SVG_URL, "la imagen del enunciado")
    assert partes[0]["type"] == "input_text"
    assert "Desempleo (%) | 15,9 | 2020" in partes[0]["text"]


def test_imagen_normal_pasa_tal_cual():
    assert imagenes.partes_imagen("https://x/y.png", "img")[0]["image_url"] == "https://x/y.png"


def test_turno_con_svg_no_manda_svg_al_modelo(modelo, monkeypatch):
    llamadas, respuestas = modelo
    monkeypatch.setattr(imagenes, "_svg_a_png", lambda svg: b"PNG")
    respuestas.append({"reply": "¿Qué muestra el eje vertical de la gráfica?", "avanzar": False})
    cuerpo = guia()
    cuerpo["question"] = {**PREGUNTA, "imageUrl": SVG_URL}
    cliente.post("/", json=cuerpo)
    urls = [p.get("image_url", "") for p in llamadas[0]["contenido"]]
    assert all("svg" not in u for u in urls) and any(u.startswith("data:image/png") for u in urls)
