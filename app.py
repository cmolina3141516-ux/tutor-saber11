import streamlit as st
import openai
import os
import time
import base64
import re
from datetime import datetime
from PIL import Image
import io

# ==========================================
# CONFIGURACIÓN INICIAL
# ==========================================
st.set_page_config(
    page_title="Tutor Saber 11° Pro - Profesor Marco",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ==========================================
# INICIALIZACIÓN DE ESTADOS
# ==========================================
if 'agente_activado' not in st.session_state:
    st.session_state.agente_activado = False
if 'start_time' not in st.session_state:
    st.session_state.start_time = None
    st.session_state.time_limit = 15 * 60  # 15 minutos
    st.session_state.warning_shown = False
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'current_image' not in st.session_state:
    st.session_state.current_image = None
if 'language' not in st.session_state:
    st.session_state.language = 'es-CO'
if 'bloqueado' not in st.session_state:
    st.session_state.bloqueado = False

# ==========================================
# CSS Personalizado avanzado
# ==========================================
st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: bold;
        color: #1f4788;
        text-align: center;
        margin-bottom: 0.5rem;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.1);
    }
    .activation-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-height: 80vh;
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        border-radius: 20px;
        padding: 40px;
        box-shadow: 0 10px 40px rgba(0,0,0,0.1);
    }
    .professor-img {
        border-radius: 50%;
        box-shadow: 0 8px 32px rgba(31, 71, 136, 0.3);
        transition: transform 0.3s ease, box-shadow 0.3s ease;
        cursor: pointer;
        border: 5px solid white;
        max-width: 300px;
        margin: 20px auto;
    }
    .professor-img:hover {
        transform: scale(1.05);
        box-shadow: 0 12px 40px rgba(31, 71, 136, 0.4);
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
        box-shadow: 0 4px 15px rgba(31, 71, 136, 0.4);
        transition: all 0.3s ease;
        margin-top: 20px;
    }
    .activate-btn:hover {
        transform: translateY(-3px);
        box-shadow: 0 6px 20px rgba(31, 71, 136, 0.6);
        background: linear-gradient(135deg, #2c5aa0 0%, #1f4788 100%);
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
        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
    }
    .chat-container {
        max-height: 60vh;
        overflow-y: auto;
        padding: 20px;
        border-radius: 15px;
        background: #f8f9fa;
        margin: 20px 0;
    }
    .warning-box {
        background: linear-gradient(135deg, #ff6b6b, #ee5a6f);
        color: white;
        padding: 20px;
        border-radius: 15px;
        text-align: center;
        font-weight: bold;
        margin: 10px 0;
        border: 3px solid #fff;
        box-shadow: 0 4px 15px rgba(238,90,111,0.3);
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.02); }
    }
    .voice-btn {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%) !important;
        color: white !important;
        border-radius: 50% !important;
        width: 60px !important;
        height: 60px !important;
        font-size: 24px !important;
        border: none !important;
        box-shadow: 0 4px 15px rgba(102,126,234,0.4) !important;
        transition: transform 0.2s !important;
    }
    .voice-btn:hover {
        transform: scale(1.1) !important;
    }
    .stProgress > div > div > div {
        transition: width 1s ease-in-out;
    }
    .welcome-text {
        font-size: 1.1rem;
        color: #555;
        text-align: center;
        max-width: 600px;
        margin: 20px auto;
        line-height: 1.6;
    }
    .features-list {
        background: white;
        padding: 20px;
        border-radius: 15px;
        margin: 20px auto;
        max-width: 500px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# SISTEMA DE VALIDACIÓN ESTRICTA
# ==========================================
KEYWORDS_SABER11 = {
    'matematicas': ['matemática', 'álgebra', 'geometría', 'trigonometría', 'estadística', 'probabilidad', 
                   'cálculo', 'número', 'ecuación', 'función', 'gráfica', 'logaritmo', 'exponencial', 
                   'geometría analítica', 'triángulo', 'círculo', 'área', 'volumen', 'perímetro', 'seno', 'coseno'],
    'lectura': ['lectura', 'comprensión', 'texto', 'crítica', 'inferencia', 'hipótesis', 'argumento', 
               'síntesis', 'análisis textual', 'literatura', 'poesía', 'ensayo', 'autor', 'tema', 
               'propósito', 'contexto', 'sinónimo', 'antónimo', 'paráfrasis', 'metáfora', 'símil'],
    'naturales': ['biología', 'física', 'química', 'ciencias naturales', 'ecología', 'genética', 
                 'célula', 'energía', 'movimiento', 'átomo', 'molécula', 'cuerpo humano', 'ecosistema',
                 'fotosíntesis', 'evolución', 'newton', 'electricidad', 'ósmosis', 'ADN', 'genoma'],
    'sociales': ['historia', 'geografía', 'ciencias sociales', 'política', 'economía', 'constitución', 
                'democracia', 'derechos humanos', 'colombia', 'guerra', 'paz', 'globalización', 
                'independencia', 'bolívar', 'territorio', 'población', 'cultura', 'cívica', 'nación'],
    'ingles': ['inglés', 'english', 'grammar', 'vocabulary', 'reading', 'listening', 'verb', 'tense', 
              'conditional', 'modal', 'preposition', 'adjective', 'noun', 'sentence', 'comprehension'],
    'generales': ['icfes', 'saber', 'prueba', 'examen', 'universidad', 'preuniversitario', 'académico', 
                 'estudio', 'preparación', 'pregunta', 'opción múltiple', 'respuesta', 'ejercicio', 
                 'problema', 'solución', 'simulacro', 'puntaje', 'aptitud', 'prueba saber']
}

def validar_contenido_saber11(texto):
    """Valida estrictamente que el contenido sea relacionado con Prueba Saber 11"""
    if not texto or len(texto.strip()) < 3:
        return True, ""
        
    texto_lower = texto.lower()
    
    for categoria, palabras in KEYWORDS_SABER11.items():
        for palabra in palabras:
            if palabra in texto_lower:
                return True, ""
    
    mensaje_advertencia = """
    ⚠️ **¡CONTENIDO NO PERMITIDO!** ⚠️
    
    Este tutor está especializado **EXCLUSIVAMENTE** en la Prueba Saber 11° (ICFES).
    
    **Áreas académicas permitidas:**
    - 📊 Matemáticas (Álgebra, Geometría, Estadística)
    - 📖 Lectura Crítica (Comprensión, Análisis textual)
    - 🧪 Ciencias Naturales (Biología, Física, Química)
    - 🌍 Ciencias Sociales (Historia, Geografía, Constitución)
    - 🗣️ Inglés (Gramática, Reading, Vocabulario)
    
    **Ejemplos de preguntas válidas:**
    - "¿Cómo resuelvo ecuaciones cuadráticas?"
    - "Analiza este texto argumentativo"
    - "¿Qué es la fotosíntesis?"
    - "Explica la Independencia de Colombia"
    - "¿Cuándo uso present perfect?"
    
    Por favor, reformula tu pregunta relacionándola con estas áreas académicas.
    """
    return False, mensaje_advertencia

# ==========================================
# CONFIGURACIÓN DE API GROQ (CAMBIO AQUÍ)
# ==========================================
def get_groq_client():
    api_key = os.getenv("GROQ_API_KEY")  # Cambiado de KIMI_API_KEY
    if not api_key:
        st.error("🔑 API Key no configurada. Contacta a tu profesor.")
        st.stop()
    
    return openai.OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1"  # URL de Groq
    )

# ==========================================
# PANTALLA DE ACTIVACIÓN (IMAGEN PROFESOR MARCO)
# ==========================================
if not st.session_state.agente_activado:
    st.markdown("""
    <div class="activation-container">
        <h1 style="color: #1f4788; margin-bottom: 10px;">🎓 Tutor Saber 11° Pro</h1>
        <p style="font-size: 1.2rem; color: #666; margin-bottom: 30px;">Tu asistente personal para la prueba ICFES</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Imagen del Profesor Marco centrada y clickeable
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # URL de la imagen proporcionada
        imagen_profesor = "https://i.postimg.cc/vmkMbL49/PROFESOR-MARCO-AGENTE-PARA-PRUEBA-SABER.png"
        
        # Mostrar imagen con enlace para activar
        st.markdown(f"""
        <div style="text-align: center;">
            <img src="{imagen_profesor}" class="professor-img" width="280" 
                 style="cursor: pointer;" id="profesor-img">
            <p style="font-size: 0.9rem; color: #888; margin-top: 10px;">
                👆 Haz clic en la imagen para comenzar
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Botón oficial de activación debajo de la imagen
        if st.button("🚀 ACTIVAR AGENTE TUTOR", key="activate_btn", use_container_width=True):
            st.session_state.agente_activado = True
            st.session_state.start_time = time.time()
            st.rerun()
    
    # Características en la pantalla de inicio
    st.markdown("""
    <div class="features-list">
        <h4 style="text-align: center; color: #1f4788; margin-bottom: 15px;">✨ Características</h4>
        <ul style="list-style: none; padding: 0;">
            <li>🎤 <strong>Reconocimiento de voz:</strong> Habla con el tutor</li>
            <li>📸 <strong>Análisis de imágenes:</strong> Sube capturas de pantalla</li>
            <li>⏱️ <strong>Sesiones de 15 min:</strong> Entrenamiento enfocado</li>
            <li>🔒 <strong>Contenido exclusivo:</strong> Solo temas ICFES</li>
            <li>🌐 <strong>Multiidioma:</strong> Español, English, Português</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    st.stop()  # Detener aquí hasta que se active

# ==========================================
# AGENTE ACTIVADO - INTERFAZ PRINCIPAL
# ==========================================

# Verificar tiempo si está activo
if st.session_state.start_time:
    elapsed = time.time() - st.session_state.start_time
    remaining = st.session_state.time_limit - elapsed
    progress = elapsed / st.session_state.time_limit
    
    if progress >= 1:
        st.session_state.bloqueado = True

# Barra de progreso de tiempo fija en la parte superior
if not st.session_state.bloqueado:
    progress = elapsed / st.session_state.time_limit if st.session_state.start_time else 0
    remaining = st.session_state.time_limit - elapsed if st.session_state.start_time else 900
    
    col1, col2, col3 = st.columns([1, 3, 1])
    with col2:
        if progress < 0.5:
            emoji = "🟢"
        elif progress < 0.8:
            emoji = "🟡"
        else:
            emoji = "🔴"
            
        st.progress(min(progress, 1.0), text=f"{emoji} Progreso de tu sesión de entrenamiento (15 min)")
        
        if progress > 0.8 and not st.session_state.warning_shown:
            st.warning("⚠️ Últimos minutos de sesión. ¡Concéntrate en lo más importante!")
            st.session_state.warning_shown = True
else:
    st.markdown("""
    <div class='time-warning'>
        ⏰ SESSIÓN FINALIZADA - Tiempo de entrenamiento agotado (15 minutos)
    </div>
    """, unsafe_allow_html=True)
    st.error("### 🚫 Debes descansar antes de una nueva sesión")
    st.info("💡 **Tip científico:** Estudios demuestran que 15 min de estudio intenso + descanso mejoran la retención.")
    
    if st.button("🔄 Iniciar Nueva Sesión", type="primary"):
        for key in ['agente_activado', 'start_time', 'messages', 'bloqueado', 'warning_shown']:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()
    st.stop()

# Header principal
st.markdown('<div class="main-header">🎓 Tutor Saber 11° Pro - Profesor Marco</div>', unsafe_allow_html=True)
st.markdown("""
<div style="text-align: center; color: #666; margin-bottom: 20px;">
    Especialista ICFES multimodal | Voz + Texto + Imágenes | 15 min por sesión
</div>
""", unsafe_allow_html=True)

# Selector de idioma para voz
lang_col1, lang_col2, lang_col3 = st.columns([2, 2, 2])
with lang_col2:
    idioma_seleccionado = st.selectbox(
        "🌐 Idioma para respuestas de voz:",
        options=["Español", "English", "Português"],
        index=0
    )
    lang_codes = {"Español": "es-CO", "English": "en-US", "Português": "pt-BR"}
    st.session_state.language = lang_codes[idioma_seleccionado]

# Mensaje inicial del sistema (solo una vez)
if len(st.session_state.messages) == 0:
    system_msg = """Eres el Profesor Marco, un tutor experto en la Prueba Saber 11° (ICFES) de Colombia. 
    Tu misión es ayudar a estudiantes de grado 11° a prepararse exitosamente.
    
    REGLAS ESTRICTAS:
    1. Solo respondes temas relacionados con: Matemáticas, Lectura Crítica, Ciencias Naturales, Ciencias Sociales e Inglés.
    2. Si te preguntan algo fuera de estos temas, responde: "Solo puedo ayudarte con temas de la Prueba Saber 11. ¿Tienes alguna duda sobre matemáticas, lectura, ciencias o inglés?"
    3. Estructura: Concepto → Explicación → Ejemplo → Tip ICFES.
    4. Siempre incluye estrategias de resolución de pruebas tipo ICFES.
    5. Tono: Profesional, motivador, claro y académico."""
    
    welcome_msg = "¡Hola! Soy el Profesor Marco 👨‍🏫. Estoy aquí para ayudarte a dominar la Prueba Saber 11°. Tienes 15 minutos de sesión enfocada. ¿En qué área necesitas ayuda hoy? Puedes escribirme, hablarme o subir imágenes de ejercicios."
    
    st.session_state.messages = [
        {"role": "system", "content": system_msg},
        {"role": "assistant", "content": welcome_msg}
    ]

# ==========================================
# ÁREA DE IMÁGENES (Upload + Paste)
# ==========================================
st.markdown("### 📸 Análisis de Imágenes")
img_col1, img_col2 = st.columns(2)

with img_col1:
    uploaded_file = st.file_uploader(
        "Sube captura de pantalla o foto del ejercicio", 
        type=['png', 'jpg', 'jpeg'],
        key="file_uploader"
    )
    
    if uploaded_file:
        image = Image.open(uploaded_file)
        st.session_state.current_image = image
        st.image(image, caption="Imagen cargada", use_container_width=True)

with img_col2:
    st.markdown("**O pega imagen desde el portapapeles (
