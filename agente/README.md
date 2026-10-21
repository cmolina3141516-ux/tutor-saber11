# Marco: agente-tutor socrático (contrato v4, dos vueltas)

Servicio HTTP que la plataforma Prueba Saber 11 llama desde `TUTOR_AGENT_URL`. Implementa el
contrato v4 (`docs/tutor-agent-contract.md` en el repositorio de la plataforma: entrenamiento en dos vueltas) con OpenAI
`gpt-5.4-mini`.

La app Streamlit de la raíz (`app.py`, desplegada en Render) es otro producto y no se toca aquí.

## Archivos
| Archivo | Qué hace |
|---|---|
| `contrato.py` | Tipos del contrato v4 (espejo de `src/tutor/contract.ts`). |
| `instrucciones.py` | Instrucciones de Marco para el turno guiado y la revisión. Aquí se mejora el comportamiento. |
| `perfil.py` | Resume el progreso del estudiante en un nivel por área y componente. |
| `guardia.py` | Segunda barrera: detecta mensajes guiados que suenan a veredicto. |
| `respaldo.py` | Mensajes fijos si el modelo falla o insiste en dar veredictos (iguales al respaldo de la plataforma). |
| `modelo.py` | Llamada a OpenAI con salida JSON estructurada. |
| `servicio.py` | Rutas: `POST /` (contrato) y `GET /salud`. |

## Variables de entorno
| Variable | Valor |
|---|---|
| `OPENAI_API_KEY` | Clave de OpenAI (en Cloud Run, desde Secret Manager). |
| `TUTOR_AGENT_KEY` | La misma llave que la plataforma pone en `TUTOR_AGENT_KEY`. Vacía = sin llave (solo local). |
| `OPENAI_MODEL` | Opcional. Por defecto `gpt-5.4-mini`. |
| `REASONING_EFFORT_GUIDE` / `REASONING_EFFORT_REVIEW` | Opcional. Por defecto `low` (rápido y barato; la plataforma espera 20 s). |

## Probar en local
```bash
python -m venv .venv-agente
.venv-agente/Scripts/python -m pip install -r agente/requirements.txt pytest httpx
.venv-agente/Scripts/python -m pytest -q
OPENAI_API_KEY=... .venv-agente/Scripts/python -m uvicorn agente.servicio:app --port 8765
```
Con el servidor local, en el `.env` de la plataforma: `TUTOR_AGENT_URL=http://localhost:8765/`.

## Desplegar en Cloud Run
Requisitos: Google Cloud CLI (`gcloud`) con sesión iniciada y un proyecto con facturación activa.

```bash
gcloud config set project <PROYECTO>
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com

# Claves en Secret Manager (se escriben desde un archivo, nunca en la línea de comandos)
gcloud secrets create openai-api-key --data-file=<archivo con la clave de OpenAI>
gcloud secrets create tutor-agent-key --data-file=<archivo con la llave compartida>

gcloud run deploy marco-tutor --source . --region us-central1 \
  --allow-unauthenticated \
  --set-secrets OPENAI_API_KEY=openai-api-key:latest,TUTOR_AGENT_KEY=tutor-agent-key:latest \
  --memory 512Mi --cpu 1 --min-instances 0 --max-instances 5 --timeout 30
```
`--allow-unauthenticated` deja la URL pública, pero el servicio exige `Authorization: Bearer <TUTOR_AGENT_KEY>`.
Para dar acceso a la cuenta de servicio de Cloud Run a los secretos:
`gcloud secrets add-iam-policy-binding <secreto> --member=serviceAccount:<PROYECTO_NUM>-compute@developer.gserviceaccount.com --role=roles/secretmanager.secretAccessor`.

Después, en la plataforma: `TUTOR_AGENT_URL=<URL de Cloud Run>/` y `TUTOR_AGENT_KEY=<la misma llave>`.
