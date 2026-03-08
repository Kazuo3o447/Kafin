FROM python:3.11-slim

WORKDIR /app

# Python-Abhängigkeiten
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Anwendung
COPY backend/app /app/backend/app
COPY schemas /app/schemas

ENV PYTHONPATH=/app

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
