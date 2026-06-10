FROM python:3.11-slim
WORKDIR /app

# Install engine
COPY packages/nse_engine /app/nse_engine_pkg
RUN pip install --no-cache-dir -e /app/nse_engine_pkg

# Install backend dependencies
COPY apps/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/backend /app
COPY packages/nse_engine /app/packages/nse_engine

ENV PYTHONPATH="/app/packages/nse_engine:${PYTHONPATH}"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
