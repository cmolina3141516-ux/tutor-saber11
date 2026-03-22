import streamlit as st
import openai
import os
import time
from datetime import datetime

# ==========================================
# CONFIGURACIÓN
# ==========================================
st.set_page_config(
    page_title="Tutor Saber 11° Pro - Profesor Marco",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: bold;
        color: #1f4788;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .time-warning {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        background: linear-gradient(90deg, #ff6b6b, #feca57);
        color: white;
        padding: 10px;
        text-align: center;
        font-weight: bold;
        z-index: 9999;
    }
    .warning-box {
        background: linear-gradient(135deg, #ff6b6b, #ee5a6f);
        color: white;
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        font-weight: bold;
        margin: 10px 0;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.02); }
    }
    .professor-img {
        border-radius: 50%;
        box-shadow: 0 8px 32px rgba(31, 71, 136, 0.3);
        cursor: pointer;
        border: 5px solid white;
        max-width: 300px;
        margin: 20px auto;
        display: block;
    }
    .activate-btn {
        background: linear-gradient(135deg, #1f4788 0%, #2c5aa0 100%);
        color: white;
        padding: 20px 40px;
        font-size: 1.3rem;
        font-weight: bold;
        border: none;
        border-radius: 50px;
        cursor: pointer;
        margin-top: 20px;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# ESTADOS
# ==========================================
if 'agente_activado' not in st.session_state:
    st.session_state.agente_activado = False
if 'start_time' not in st.session_state:
    st.session_state.start_time = None
    st.session_state.time_limit = 15 * 60
    st.session_state.warning_shown = False
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'language' not in st.session_state:
    st.session_state.language = 'es-CO'
if 'bloqueado' not in st.session_state:
    st.session_state.bloqueado = False

# ==========================================
# VALIDACIÓN DE CONTENIDO
# ==========================================
KEYWORDS_SABER11 = [
    'matemática', 'álgebra', 'geometría', 'trigonometría', 'estadística', 'probabilidad', 
    'lectura', 'comprensión', 'texto', 'crítica', 'inferencia', 'argumento', 
    'biología', 'física', 'química', 'ciencias naturales', 'célula', 'energía', 
    'historia', 'geografía', 'ciencias sociales', 'política', 'economía', 'constitución', 
    'inglés', 'english', 'grammar', 'vocabulary', 'reading',
    'icfes', 'saber', 'prueba', 'examen', 'universidad', 'académico', 
    'estudio', 'preparación', 'pregunta', 'respuesta', 'ejercicio', 'problema'
]

def validar_contenido(texto):
    if not texto or len(texto.strip()) < 3:
        return True, ""
    
    texto_lower = texto.lower()
    for palabra in KEYWORDS_SABER11:
        if palabra in texto_lower:
            return True, ""
    
    return False, "⚠️ Solo puedo ayudarte con temas de la Prueba Saber 11 (Matemáticas, Lectura, Ciencias, Sociales, Inglés)"

# ==========================================
# API GROQ
# ==========================================
def get_groq_client():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        st.error("🔑 API Key no configurada")
        st.stop()
    
    return openai.OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1"
    )

# ==========================================
# PANTALLA DE INICIO
# ==========================================
if not st.session_state.agente_activado:
    st.markdown('<div class="main-header">🎓 Tutor Saber 11° Pro</div>', unsafe_allow_html=True)
    st.markdown('<div style="text-align: center; color: #666; margin-bottom: 30px;">Tu asistente personal para la prueba ICFES</div>', unsafe_allow_html=True)
    
    # Imagen Profesor Marco
    imagen_profesor = "https://i.postimg.cc/vmkMbL49/PROFESOR-MARCO-AGENTE-PARA-PRUEBA-SABER.png"
    st.markdown(f'<img src="{imagen_profesor}" class="professor-img">', unsafe_allow_html=True)
    st.markdown('<div style="text-align: center; margin-bottom: 20px;"><strong>👆 Haz clic abajo para comenzar</strong></div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🚀 ACTIVAR AGENTE TUTOR", use_container_width=True):
            st.session_state.agente_activado = True
            st.session_state.start_time = time.time()
            st.rerun()
    
    st.markdown("""
    <div style="background: white; padding: 20px; border-radius: 15px; margin: 20px auto; max-width: 500px;">
        <h4 style="text-align: center; color: #1f4788;">✨ Características</h4>
        <ul>
            <li>🎤 <strong>Voz:</strong> Habla con el tutor</li>
            <li>⏱️ <strong>15 min:</strong> Sesiones enfocadas</li>
            <li>🔒 <strong>Solo ICFES:</strong> Contenido exclusivo</li>
            <li>🌐 <strong>Multiidioma:</strong> Español, English, Português</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    st.stop()

# ==========================================
# TEMPORIZADOR
# ==========================================
if st.session_state.start_time:
    elapsed = time.time() - st.session_state.start_time
    remaining = st.session_state.time_limit - elapsed
    progress = elapsed / st.session_state.time_limit
    
    if progress >= 1:
        st.session_state.bloqueado = True

if not st.session_state.bloqueado:
    progress = elapsed / st.session_state.time_limit if st.session_state.start_time else 0
    remaining = st.session_state.time_limit - elapsed if st.session_state.start_time else 900
    
    col1, col2, col3 = st.columns([1, 3, 1])
    with col2:
        emoji = "🟢" if progress < 0.5 else "🟡" if progress < 0.8 else "🔴"
        st.progress(min(progress, 1.0), text=f"{emoji} Progreso de tu sesión (15 min)")
        
        if progress > 0.8 and not st.session_state.warning_shown:
            st.warning("⚠️ Últimos minutos de sesión")
            st.session_state.warning_shown = True
else:
    st.error("### ⏰ Sesión finalizada")
    st.info("Recarga la página para comenzar otra sesión")
    if st.button("🔄 Nueva Sesión"):
        for key in ['agente_activado', 'start_time', 'messages', 'bloqueado', 'warning_shown']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()
    st.stop()

# ==========================================
# INTERFAZ PRINCIPAL
# ==========================================
st.markdown('<div class="main-header">🎓 Tutor Saber 11° Pro - Profesor Marco</div>', unsafe_allow_html=True)

# Selector de idioma
col1, col2, col3 = st.columns([2, 2, 2])
with col2:
    idioma = st.selectbox("🌐 Idioma para voz:", ["Español", "English", "Português"], index=0)
    lang_codes = {"Español": "es-CO", "English": "en-US", "Português": "pt-BR"}
    st.session_state.language = lang_codes[idioma]

# Mensaje inicial
if len(st.session_state.messages) == 0:
    welcome = "¡Hola! Soy el Profesor Marco 👨‍🏫. Estoy aquí para ayudarte con la Prueba Saber 11°. Tienes 15 minutos. ¿En qué área necesitas ayuda?"
    st.session_state.messages = [
        {"role": "system", "content": "Eres el Profesor Marco, experto en ICFES Colombia. Solo respondes temas de: Matemáticas, Lectura Crítica, Ciencias Naturales, Ciencias Sociales e Inglés. Estructura: Concepto → Explicación → Ejemplo → Tip ICFES."},
        {"role": "assistant", "content": welcome}
    ]

# Mostrar chat
for i, msg in enumerate(st.session_state.messages):
    if msg['role'] == 'system':
        continue
    elif msg['role'] == 'user':
        with st.chat_message("user", avatar="👨‍🎓"):
            st.write(msg['content'])
    else:
        with st.chat_message("assistant",
