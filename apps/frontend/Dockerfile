FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md /app/
COPY apps /app/apps
COPY agents /app/agents
COPY pipeline /app/pipeline
COPY data /app/data
RUN pip install --no-cache-dir -e .

CMD ["streamlit", "run", "apps/frontend/app.py", "--server.address", "0.0.0.0", "--server.port", "8501"]
