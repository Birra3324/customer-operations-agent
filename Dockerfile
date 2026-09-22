FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_ENV=production \
    AI_PROVIDER=heuristic \
    DATABASE_URL=sqlite:////var/lib/ops/ops.db \
    FIXTURES_DIR=data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY data ./data

RUN mkdir -p /var/lib/ops

EXPOSE 8789

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8789"]
