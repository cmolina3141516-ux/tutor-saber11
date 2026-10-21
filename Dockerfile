# Marco, agente-tutor socrático (contrato v3). Se despliega en Cloud Run.
# La app Streamlit (app.py) sigue desplegándose aparte en Render y no entra en esta imagen.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY agente/requirements.txt agente/requirements.txt
RUN pip install --no-cache-dir -r agente/requirements.txt
COPY agente agente
CMD exec uvicorn agente.servicio:app --host 0.0.0.0 --port ${PORT:-8080}
