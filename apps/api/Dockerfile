FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md /app/
COPY apps /app/apps
COPY agents /app/agents
COPY pipeline /app/pipeline
COPY data /app/data
COPY scripts /app/scripts
RUN pip install --no-cache-dir -e .

CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
