import streamlit as st
import openai
import os
import time

st.set_page_config(page_title="Tutor Saber 11° - Profesor Marco", page_icon="🎓", layout="wide")

# CSS
st.markdown("""
<style>
    .main-header { font-size: 2.5rem; font-weight: bold; color: #1f4788; text-align: center; }
    .professor-img { border-radius: 50%; max-width: 280px; margin: 20px auto; display: block; box-shadow: 0 8px 32px rgba(31,71,136,0.3); }
    .warning-box { background: linear-gradient(135deg, #ff6b6b, #ee5a6f); color: white; padding: 20px; border-radius: 15px; text-align: center; font-weight: bold; animation: pulse 2s infinite; }
    @keyframes pulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.02); } }
</style>
""", unsafe_allow_html=True)

# Estados
if 'agente_activado' not in st.session_state:
    st.session_state.agente_activado = False
    st.session_state.start_time = None
    st.session_state.time_limit = 15 * 60
    st.session_state.messages = []
    st.session_state.language = 'es-CO'

# Validación
KEYWORDS = ['matemática', 'álgebra', 'geometría', 'trigonometría', 'estadística', 'lectura', 'comprensión', 'texto', 'biología', 'física', 'química', 'historia', 'geografía', 'inglés', 'english', 'icfes', 'saber', 'prueba', 'examen']

def validar(texto):
    if not texto: return True, ""
    texto_lower = texto.lower()
    for palabra in KEYWORDS:
        if palabra in texto_lower:
            return True, ""
    return False, "⚠️ Solo puedo ayudarte con temas de la Prueba Saber 11 (Matemáticas, Lectura, Ciencias, Sociales, Inglés)"

# API
def get_client():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        st.error("API Key no configurada")
        st.stop()
    return openai.OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")

# PANTALLA DE INICIO
if not st.session_state.agente_activado:
    st.markdown('<div class="main-header">🎓 Tutor Saber 11° Pro</div>', unsafe_allow_html=True)
    st.markdown('<div style="text-align:center; color:#666; margin-bottom:20px;">Tu asistente personal para la prueba ICFES</div>', unsafe_allow_html=True)
    
    imagen = "https://i.postimg.cc/vmkMbL49/PROFESOR-MARCO-AGENTE-PARA-PRUEBA-SABER.png"
    st.markdown(f'<img src="{imagen}" class="professor-img">', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        if st.button("🚀 ACTIVAR AGENTE TUTOR", use_container_width=True):
            st.session_state.agente_activado = True
            st.session_state.start_time = time.time()
            st.rerun()
    
    st.markdown("""
    <div style="background:white; padding:20px; border-radius:15px; max-width:500px; margin:20px auto; box-shadow:0 4px 12px rgba(0,0,0,0.1);">
        <h4 style="color:#1f4788; text-align:center;">✨ Características</h4>
        <ul>
            <li>🎤 Reconocimiento de voz</li>
            <li>⏱️ Sesiones de 15 minutos enfocadas</li>
            <li>🔒 Solo contenido ICFES</li>
            <li>🌐 Español, English, Português</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    st.stop()

# TEMPORIZADOR
elapsed = time.time() - st.session_state.start_time if st.session_state.start_time else 0
progress = elapsed / st.session_state.time_limit

if progress >= 1:
    st.error("### ⏰ Sesión finalizada (15 minutos)")
    if st.button("🔄 Nueva Sesión"):
        for key in ['agente_activado', 'start_time', 'messages']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()
    st.stop()

col1, col2, col3 = st.columns([1,3,1])
with col2:
    emoji = "🟢" if progress < 0.5 else "🟡" if progress < 0.8 else "🔴"
    st.progress(min(progress, 1.0), text=f"{emoji} Progreso de sesión (15 min)")
    if progress > 0.8:
        st.warning("⚠️ Últimos minutos")

# INTERFAZ
st.markdown('<div class="main-header">🎓 Tutor Saber 11° - Profesor Marco</div>', unsafe_allow_html=True)

col1, col2, col3 = st.columns([2,2,2])
with col2:
    idioma = st.selectbox("🌐 Idioma:", ["Español", "English", "Português"], index=0)
    lang_codes = {"Español": "es-CO", "English": "en-US", "Português": "pt-BR"}
    st.session_state.language = lang_codes[idioma]

if len(st.session_state.messages) == 0:
    welcome = "¡Hola! Soy el Profesor Marco 👨‍🏫. Estoy aquí para ayudarte con la Prueba Saber 11°. ¿En qué área necesitas ayuda?"
    st.session_state.messages = [
        {"role": "system", "content": "Eres Profesor Marco, experto ICFES Colombia. Solo respondes: Matemáticas, Lectura Crítica, Ciencias Naturales, Ciencias Sociales, Inglés. Estructura: Concepto→Explicación→Ejemplo→Tip ICFES."},
        {"role": "assistant", "content": welcome}
    ]

# Chat
for i, msg in enumerate(st.session_state.messages):
    if msg['role'] == 'system':
        continue
    elif msg['role'] == 'user':
        with st.chat_message("user", avatar="👨‍🎓"):
            st.write(msg['content'])
    else:
        with st.chat_message("assistant", avatar="👨‍🏫"):
            st.write(msg['content'])
            if st.button("🔊 Escuchar", key=f"tts_{i}"):
                texto = msg['content'].replace('"', '\\"').replace('\n', ' ')
                st.components.v1.html(f"""
                <script>
                    if ('speechSynthesis' in window) {{
                        var msg = new SpeechSynthesisUtterance();
                        msg.text = "{texto}";
                        msg.lang = "{st.session_state.language}";
                        msg.rate = 0.9;
                        window.speechSynthesis.speak(msg);
                    }}
                </script>
                """, height=0)

# Input
prompt = st.chat_input("Escribe tu pregunta sobre Saber 11°...")
if prompt:
    es_valido, error = validar(prompt)
    if not es_valido:
        st.markdown(f"<div class='warning-box'>{error}</div>", unsafe_allow_html=True)
    else:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("assistant", avatar="👨‍🏫"):
            with st.spinner("🧠 Profesor Marco está pensando..."):
                try:
                    client = get_client()
                    api_messages = [{"role": m['role'], "content": m['content']} for m in st.session_state.messages if m['role'] != 'system']
                    api_messages.insert(0, {"role": "system", "content": "Eres Profesor Marco, experto ICFES. Solo temas de Matemáticas, Lectura, Ciencias Naturales, Ciencias Sociales, Inglés."})
                    
                    response = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=api_messages,
                        temperature=0.7,
                        max_tokens=2048
                    )
                    respuesta = response.choices[0].message.content
                    st.write(respuesta)
                    st.session_state.messages.append({"role": "assistant", "content": respuesta})
                except Exception as e:
                    st.error(f"Error: {str(e)}")
        st.rerun()

st.divider()
st.markdown('<div style="text-align:center; color:#666; font-size:0.8rem;">🔒 Tutor ICFES | Profesor Marco | Groq AI</div>', unsafe_allow_html=True)
