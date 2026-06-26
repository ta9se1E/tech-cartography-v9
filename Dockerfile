# v8 Cloud Run — minimal Dockerfile (Phase27N prepare only — do not build in this phase)
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_UI_VERSION=v8 \
    DISABLE_EMAIL_SEND=true \
    DISABLE_SCHEDULER=true \
    LIVE_OUTPUTS_ROOT=/tmp/tech_cartography_outputs

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY Procfile .
COPY src/ src/
COPY cases/ cases/

EXPOSE 8080

CMD streamlit run app.py \
  --server.address=0.0.0.0 \
  --server.port=${PORT:-8080} \
  --server.headless=true \
  --server.fileWatcherType=none \
  --browser.gatherUsageStats=false
