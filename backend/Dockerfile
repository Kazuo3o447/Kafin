FROM python:3.11-slim

# Kafin v6.1.4 - Prompt Quality + Modell-Optimierung
# Aktuelle Features: API Usage Tracking, Prompt Quality v0.4, DeepSeek Modell-Matrix

WORKDIR /app

# Python-Abhängigkeiten
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Modell vorladen (verhindert Download zur Laufzeit)
RUN python -c "from transformers import AutoModelForSequenceClassification, AutoTokenizer; AutoModelForSequenceClassification.from_pretrained('ProsusAI/finbert'); AutoTokenizer.from_pretrained('ProsusAI/finbert')"

# Anwendung
ARG CACHEBUST=1
COPY backend/app /app/backend/app
COPY schemas /app/schemas

ENV PYTHONPATH=/app

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
