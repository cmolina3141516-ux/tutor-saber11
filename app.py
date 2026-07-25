import json
import os
import time
from datetime import datetime

import openai
import streamlit as st


st.set_page_config(page_title="Ruta Saber 11 | Profesor Marco", page_icon="🎓", layout="wide")

AREAS = {
    "Lectura Crítica": "interpretación, inferencia y evaluación de argumentos",
    "Matemáticas": "interpretación, formulación, ejecución y argumentación",
    "Sociales y Ciudadanas": "pensamiento social, análisis de perspectivas y deliberación",
    "Ciencias Naturales": "conocimiento científico, explicación de fenómenos e indagación",
    "Inglés": "comprensión de lectura, vocabulario e intención comunicativa",
}

RESOURCES = [
    ("Guía oficial Saber 11", "https://www.icfes.gov.co/evaluaciones-icfes/saber-11/guia-de-orientacion-examen-saber-11/"),
    ("Qué se evalúa", "https://www.icfes.gov.co/caja-de-herramientas-saber-11/que-se-evalua/"),
    ("Práctica oficial", "https://www.icfes.gov.co/caja-de-herramientas-saber-11/practica/"),
    ("Marcos de referencia", "https://www.icfes.gov.co/marcos-de-referencia-examen-saber-11/"),
]

TUTOR_AVATAR_URL = "https://i.postimg.cc/KjzQ9YPT/TUTOR-PRUEBA-SABER-11.png"


def init_state():
    values = {
        "configured": False,
        "student_name": "",
        "grade": "11°",
        "target_date": "",
        "focus_area": "Todas las áreas",
        "mode": "Práctica guiada",
        "started_at": None,
        "chat": [],
        "analysis": None,
        "simulations": {},
    }
    for key, value in values.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_state()

st.markdown(
    """
    <style>
      :root { --navy:#10253f; --blue:#176fa8; --gold:#e7ad3d; }
      .stApp { background:linear-gradient(135deg,#edf4f8,#fdfbf5); }
      .block-container { max-width:1180px; padding-top:2rem; }
      .hero { background:linear-gradient(135deg,#10253f,#1b6590); color:white; border-radius:24px; padding:2rem 2.4rem; margin-bottom:1rem; }
      .hero-grid { display:grid; grid-template-columns:minmax(0,1fr) 280px; gap:2rem; align-items:center; }
      .hero h1 { color:white; margin:0; font-size:clamp(2rem,5vw,3.7rem); }
      .hero p { color:#e5edf4; font-size:1.08rem; max-width:800px; }
      .eyebrow { color:#f0c363; font-weight:700; letter-spacing:.18em; text-transform:uppercase; }
      .hero-avatar { width:100%; max-width:280px; aspect-ratio:1; object-fit:cover; border-radius:22px; border:3px solid rgba(255,255,255,.55); box-shadow:0 18px 35px rgba(0,0,0,.22); }
      .card { background:rgba(255,255,255,.82); border:1px solid #d6e1e9; border-radius:18px; padding:1.2rem 1.4rem; margin:.6rem 0; }
      .method { border-left:5px solid var(--gold); }
      .setup-intro { position:relative; overflow:hidden; color:white; margin:1.25rem 0 1rem; padding:1.45rem 1.65rem; border-radius:24px; background:linear-gradient(135deg,#10253f 0%,#176fa8 68%,#2395c8 100%); box-shadow:0 16px 34px rgba(16,37,63,.16); }
      .setup-intro::after { content:''; position:absolute; width:180px; height:180px; right:-55px; top:-82px; border:28px solid rgba(255,255,255,.12); border-radius:50%; }
      .setup-kicker { position:relative; z-index:1; color:#f0c363; font-size:.76rem; font-weight:800; letter-spacing:.18em; text-transform:uppercase; }
      .setup-intro h2 { position:relative; z-index:1; color:white !important; margin:.35rem 0 .35rem; font-size:clamp(1.7rem,3vw,2.35rem); }
      .setup-intro p { position:relative; z-index:1; color:#e5f0f7 !important; margin:0; font-size:1.05rem; }
      .route-chips { position:relative; z-index:1; display:flex; flex-wrap:wrap; gap:.5rem; margin-top:1rem; }
      .route-chip { display:inline-flex; align-items:center; padding:.42rem .72rem; border:1px solid rgba(255,255,255,.3); border-radius:999px; color:#f7fbff; background:rgba(255,255,255,.12); font-size:.82rem; font-weight:700; }
      .attach-hint { color:#536b7d; margin:.45rem 0 .25rem; font-size:.94rem; }
      [data-testid="stForm"] { padding:1.35rem 1.45rem 1.15rem; border:1px solid #c8dce9; border-radius:24px; background:rgba(255,255,255,.78); box-shadow:0 12px 28px rgba(16,37,63,.08); }
      [data-testid="stForm"] button { background:linear-gradient(135deg,#176fa8,#0f84c5) !important; color:white !important; border:0 !important; box-shadow:0 10px 20px rgba(23,111,168,.22); transition:transform .2s ease, box-shadow .2s ease; }
      [data-testid="stForm"] button:hover { transform:translateY(-2px); box-shadow:0 14px 24px rgba(23,111,168,.3); }
      .stButton > button { border-radius:999px; font-weight:700; }
      .stTextInput label, .stSelectbox label { color:#10253f !important; font-weight:700 !important; }
      .stTextInput input, .stSelectbox [data-baseweb="select"] > div { background:#dcecf8 !important; color:#10253f !important; border-color:#a9cfe8 !important; }
      .stTextInput input::placeholder { color:#536b7d !important; opacity:1 !important; }
      .stSelectbox [data-baseweb="select"] div, .stSelectbox [data-baseweb="select"] svg { color:#10253f !important; fill:#10253f !important; }
      [data-testid="stFileUploaderDropzone"] { background:#dcecf8 !important; border:1px solid #a9cfe8 !important; border-radius:999px !important; transition:background .2s ease, border-color .2s ease, transform .2s ease; }
      [data-testid="stFileUploaderDropzone"]:hover { background:#c9e3f3 !important; border-color:#176fa8 !important; transform:translateY(-1px); }
      [data-testid="stFileUploaderDropzone"] button { background:#176fa8 !important; color:white !important; border:0 !important; border-radius:999px !important; font-weight:700 !important; }
      [data-testid="stFileUploaderDropzone"] small, [data-testid="stFileUploaderDropzone"] span { color:#10253f !important; }
      @media (max-width: 700px) { .hero-grid { grid-template-columns:1fr; } .hero-avatar { max-width:220px; } }
    </style>
    """,
    unsafe_allow_html=True,
)


def client():
    key = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        return None
    args = {"api_key": key}
    if os.getenv("GROQ_API_KEY"):
        args["base_url"] = "https://api.groq.com/openai/v1"
    return openai.OpenAI(**args)


def ask_model(messages, max_tokens=850, temperature=0.25):
    api = client()
    if api is None:
        return None
    response = api.chat.completions.create(
        model=os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"),
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()


def profile():
    return f"Estudiante: {st.session_state.student_name or 'sin nombre'} | Grado: {st.session_state.grade} | Área: {st.session_state.focus_area} | Fecha objetivo: {st.session_state.target_date or 'no definida'}"


def system_prompt():
    areas = "; ".join(f"{name}: {desc}" for name, desc in AREAS.items())
    return f"""
Eres Profesor Marco, tutor experto en la Prueba Saber 11 de Colombia. Trabajas las cinco pruebas oficiales: Lectura Crítica, Matemáticas, Sociales y Ciudadanas, Ciencias Naturales e Inglés. Competencias: {areas}.
Perfil: {profile()}

Tu objetivo es enseñar a comprender y decidir, no entregar respuestas como solucionario.
APLICA EL MÉTODO 2+2+1: primero pide identificar situación, pregunta y datos; luego ayuda a descartar dos opciones absurdas con una razón breve para cada una; después formula una sola pregunta para comparar las dos restantes; finalmente pide una elección justificada y solo entonces confirma y explica.
Haz una sola pregunta estratégica por turno para ahorrar tiempo y tokens. Si el estudiante pide explícitamente la solución, explica el razonamiento completo.
Adapta lenguaje y dificultad al grado. Detecta área, competencia, tipo de error y nivel de seguridad cuando sea posible. No inventes preguntas oficiales, fuentes ni respuestas. No des ayuda durante un simulacro activo. Si una consulta es amplia, pregunta qué aspecto desea profundizar. Responde en español, excepto en la práctica de Inglés.
""".strip()


def parse_json(text):
    if not text:
        return None
    text = text.strip().replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        left, right = text.find("["), text.rfind("]")
        if left >= 0 and right > left:
            try:
                return json.loads(text[left : right + 1])
            except json.JSONDecodeError:
                return None
    return None


def fallback(area, index):
    data = {
        "Lectura Crítica": ("Un autor afirma que una medida mejora la educación, pero solo presenta su opinión. ¿Qué debe hacer primero un lector crítico?", ["Aceptar la afirmación", "Buscar la evidencia", "Rechazarla sin leer", "Elegir la opción más larga"], 1, "Evaluación de argumentos", "La lectura crítica exige evaluar la evidencia que sostiene la tesis."),
        "Matemáticas": ("Una cantidad aumenta de 80 a 100. ¿Cuál es el aumento porcentual?", ["20%", "25%", "80%", "125%"], 1, "Razonamiento cuantitativo", "El aumento es 20 y 20/80 = 25%."),
        "Sociales y Ciudadanas": ("Una comunidad permite que los grupos afectados presenten argumentos antes de aprobar una norma. ¿Qué principio fortalece?", ["Participación ciudadana", "Censura", "Aislamiento", "Decisión secreta"], 0, "Pensamiento social", "Escuchar a los grupos afectados fortalece la deliberación."),
        "Ciencias Naturales": ("Para comprobar si la luz modifica el crecimiento de una planta, ¿qué variable debe cambiarse deliberadamente?", ["Cantidad de luz", "Conclusión", "Resultado esperado", "Nombre de la planta"], 0, "Indagación", "La variable independiente es la condición que se modifica."),
        "Inglés": ("Read: 'The library closes at six, so Ana leaves school early to return her books.' Why does Ana leave early?", ["To meet a friend", "To return her books", "To study at home", "To open the library"], 1, "Reading comprehension", "The sentence directly states the reason."),
    }
    question, options, correct, competence, explanation = data[area]
    return {"id": f"fallback-{index}", "area": area, "question": question, "options": options, "correct_index": correct, "competence": competence, "explanation": explanation}


def generate_questions(area, count=5):
    selected = list(AREAS) if area == "Todas las áreas" else [area]
    prompt = f"""
Genera {count} preguntas originales estilo Saber 11 para grado {st.session_state.grade}. Áreas permitidas: {', '.join(selected)}. No copies preguntas oficiales. Cada pregunta debe tener una sola respuesta correcta y cuatro opciones. Para Inglés, redacta en inglés. Devuelve únicamente JSON: una lista de objetos con area, question, options (4 textos), correct_index (0-3), competence y explanation.
"""
    raw = parse_json(ask_model([{"role": "system", "content": prompt}], max_tokens=2200, temperature=0.35))
    if not isinstance(raw, list):
        raw = []
    result = []
    for index, item in enumerate(raw[:count]):
        if not isinstance(item, dict) or not isinstance(item.get("options"), list) or len(item["options"]) != 4:
            continue
        correct = item.get("correct_index")
        if not isinstance(correct, int) or correct not in range(4):
            continue
        result.append({
            "id": f"question-{int(time.time())}-{index}",
            "area": str(item.get("area", selected[index % len(selected)])),
            "question": str(item.get("question", "")),
            "options": [str(option) for option in item["options"]],
            "correct_index": correct,
            "competence": str(item.get("competence", "Competencia Saber 11")),
            "explanation": str(item.get("explanation", "Revisa la relación entre los datos y la opción elegida.")),
        })
    if len(result) < count:
        result.extend(fallback(selected[index % len(selected)], index) for index in range(len(result), count))
    return result


def header():
    st.markdown(
        f"<section class='hero hero-grid'><div><div class='eyebrow'>Ruta Saber 11</div><h1>Profesor Marco</h1><p>Un guía para comprender las preguntas, tomar decisiones y mejorar tus estrategias en las cinco pruebas.</p><p style='color:#dcecf5'>{profile()}</p></div><img class='hero-avatar' src='{TUTOR_AVATAR_URL}' alt='Profesor Marco, tutor de Prueba Saber 11'></section>",
        unsafe_allow_html=True,
    )


def setup():
    st.markdown(
        "<div class='setup-intro'><div class='setup-kicker'>Tu preparación, a tu medida</div><h2>Configura tu ruta</h2><p>Cuéntame un poco sobre ti para adaptar la dificultad, las estrategias y el acompañamiento.</p><div class='route-chips'><span class='route-chip'>Nivel personalizado</span><span class='route-chip'>Cinco áreas Saber 11</span><span class='route-chip'>Progreso guiado</span></div></div>",
        unsafe_allow_html=True,
    )
    with st.form("setup"):
        name = st.text_input("Nombre", value=st.session_state.student_name, placeholder="Ej. Laura")
        grades = ["9°", "10°", "11°", "Egresado"]
        grade = st.selectbox("Grado", grades, index=grades.index(st.session_state.grade))
        areas = ["Todas las áreas"] + list(AREAS)
        area = st.selectbox("Área inicial", areas, index=areas.index(st.session_state.focus_area))
        date = st.text_input("Fecha aproximada del examen (opcional)", value=st.session_state.target_date, placeholder="Ej. agosto de 2026")
        submitted = st.form_submit_button("Comenzar ruta", use_container_width=True)
    if submitted:
        st.session_state.student_name = name.strip()
        st.session_state.grade = grade
        st.session_state.focus_area = area
        st.session_state.target_date = date.strip()
        st.session_state.configured = True
        st.session_state.started_at = time.time()
        st.session_state.chat = [{"role": "assistant", "content": f"Hola {name.strip() or 'estudiante'}. Trabajaremos con el método 2+2+1: comprender, descartar y justificar. ¿Qué área quieres practicar primero?"}]
        st.rerun()


def sidebar():
    with st.sidebar:
        st.markdown("## Tu ruta")
        st.caption(f"{st.session_state.student_name or 'Sin nombre'} · {st.session_state.grade}")
        modes = ["Práctica guiada", "Analizar una pregunta", "Simulacros", "Recursos oficiales"]
        selected = st.radio("Modo", modes, index=modes.index(st.session_state.mode))
        if selected != st.session_state.mode:
            st.session_state.mode = selected
            st.rerun()
        st.divider()
        elapsed = time.time() - st.session_state.started_at if st.session_state.started_at else 0
        remaining = max(0, 15 * 60 - int(elapsed))
        st.progress(remaining / (15 * 60), text=f"Sesión orientada {remaining // 60:02d}:{remaining % 60:02d}")
        if st.button("Reconfigurar perfil", use_container_width=True):
            st.session_state.configured = False
            st.rerun()


def guided():
    st.subheader("Práctica guiada")
    st.markdown("<div class='card method'><strong>Método 2+2+1:</strong> identifica los datos, descarta dos distractores, compara los dos restantes y justifica tu elección. El tutor no se adelanta a tu razonamiento.</div>", unsafe_allow_html=True)
    for message in st.session_state.chat:
        with st.chat_message(message["role"], avatar="🎓" if message["role"] == "assistant" else "👨‍🎓"):
            st.markdown(message["content"])
    prompt = st.chat_input("Escribe una pregunta de Saber 11...")
    if prompt:
        st.session_state.chat.append({"role": "user", "content": prompt})
        messages = [{"role": "system", "content": system_prompt()}] + st.session_state.chat[-10:]
        with st.chat_message("assistant", avatar="🎓"):
            with st.spinner("Preparando una guía breve..."):
                answer = ask_model(messages) or "No pude conectar con el tutor. Inténtalo nuevamente en unos segundos."
                st.markdown(answer)
        st.session_state.chat.append({"role": "assistant", "content": answer})
        st.rerun()


def analysis():
    st.subheader("Analizar una pregunta")
    st.write("Pega el enunciado y sus opciones, o adjunta una imagen/PDF. El tutor te ayudará a razonar sin revelar la respuesta de inmediato.")
    st.markdown("<div class='attach-hint'>Arrastra aquí una captura de pantalla de cualquier pregunta o selecciónala desde tu dispositivo.</div>", unsafe_allow_html=True)
    attachment = st.file_uploader(
        "📎 Arrastra y suelta una captura o haz clic para adjuntarla",
        type=["png", "jpg", "jpeg", "webp", "gif", "bmp", "pdf"],
        key="analysis_attachment",
        accept_multiple_files=False,
        help="Formatos aceptados: PNG, JPG, JPEG, WEBP, GIF, BMP y PDF.",
    )
    if attachment:
        if attachment.type.startswith("image/"):
            st.image(attachment, caption=f"Adjunto: {attachment.name}", use_container_width=True)
        else:
            st.info(f"PDF adjunto: {attachment.name}. Incluye también el enunciado o las opciones en el campo de texto para orientar el análisis.")
    with st.form("analysis"):
        area = st.selectbox("Área", list(AREAS))
        question = st.text_area("Enunciado", height=150)
        options = st.text_area("Opciones A, B, C y D", height=120, placeholder="A. ...\nB. ...\nC. ...\nD. ...")
        submitted = st.form_submit_button("Iniciar análisis", use_container_width=True)
    if submitted and (question.strip() or attachment):
        attachment_note = f"\nArchivo adjunto: {attachment.name}. No describas su contenido si no puedes verificarlo." if attachment else ""
        prompt = f"Área: {area}\nEnunciado: {question}\nOpciones:\n{options}{attachment_note}"
        messages = [{"role": "system", "content": system_prompt()}, {"role": "user", "content": "Aplica el método 2+2+1 a esta pregunta. No reveles todavía la respuesta.\n" + prompt}]
        with st.spinner("Identificando competencia y distractores..."):
            st.session_state.analysis = ask_model(messages) or "No pude analizar la pregunta en este momento."
    if st.session_state.analysis:
        st.markdown(f"<div class='card'>{st.session_state.analysis}</div>", unsafe_allow_html=True)


def simulations():
    st.subheader("Tres simulacros sin ayuda")
    st.warning("Durante un simulacro no hay pistas ni tutor. La discusión se habilita al finalizar.")
    areas = ["Todas las áreas"] + list(AREAS)
    for number in range(1, 4):
        key = f"sim_{number}"
        sim = st.session_state.simulations.get(key)
        st.markdown(f"### Simulacro {number}")
        if not sim:
            area = st.selectbox("Área", areas, key=f"area_{key}")
            if st.button(f"Iniciar simulacro {number}", key=f"start_{key}"):
                with st.spinner("Preparando preguntas..."):
                    st.session_state.simulations[key] = {"status": "active", "area": area, "questions": generate_questions(area), "answers": {}}
                st.rerun()
            continue
        if sim["status"] == "active":
            with st.form(f"exam_{key}"):
                answers = {}
                for index, item in enumerate(sim["questions"]):
                    st.markdown(f"**{index + 1}. [{item['area']}]** {item['question']}")
                    answers[item["id"]] = st.radio("Selecciona una opción", item["options"], key=f"choice_{key}_{index}", index=None)
                finished = st.form_submit_button("Finalizar simulacro", use_container_width=True)
            if finished:
                sim["answers"] = answers
                sim["status"] = "completed"
                st.rerun()
        else:
            score = sum(answer == item["options"][item["correct_index"]] for item in sim["questions"] for answer in [sim["answers"].get(item["id"])])
            total = len(sim["questions"])
            st.success(f"Resultado: {score}/{total} ({round(score / total * 100)}%).")
            if st.button(f"Discutir respuestas del simulacro {number}", key=f"review_{key}"):
                st.session_state.mode = "Práctica guiada"
                st.session_state.chat.append({"role": "user", "content": "Quiero discutir mis errores del simulacro aplicando el método 2+2+1."})
                st.rerun()
            with st.expander("Ver revisión"):
                for index, item in enumerate(sim["questions"]):
                    chosen = sim["answers"].get(item["id"]) or "Sin respuesta"
                    correct = item["options"][item["correct_index"]]
                    st.markdown(f"**{index + 1}.** Tu respuesta: {chosen} · Correcta: {correct}")
                    if chosen != correct:
                        st.caption(item["explanation"])


def resources():
    st.subheader("Recursos oficiales")
    st.write("La base de conocimiento debe priorizar fuentes oficiales, fechadas y verificables.")
    for title, url in RESOURCES:
        st.markdown(f"- [{title}]({url})")
    st.info("En la siguiente fase agregaremos búsqueda documentada y fragmentos relevantes, sin enviar libros completos en cada turno.")


header()
if not st.session_state.configured:
    setup()
    st.stop()

sidebar()
if st.session_state.mode == "Práctica guiada":
    guided()
elif st.session_state.mode == "Analizar una pregunta":
    analysis()
elif st.session_state.mode == "Simulacros":
    simulations()
else:
    resources()

st.divider()
started = datetime.fromtimestamp(st.session_state.started_at).strftime("%H:%M") if st.session_state.started_at else ""
st.caption(f"Ruta Saber 11 · Profesor Marco · Sesión iniciada {started}")
