FROM python:3.10-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    MODEL_DIR=/app/runtime/models

WORKDIR /app/backend

RUN groupadd --system baro && useradd --system --gid baro --home-dir /app --shell /usr/sbin/nologin baro

COPY backend/requirements.txt /tmp/requirements.txt
COPY backend/requirements-model.txt /tmp/requirements-model.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r /tmp/requirements.txt -r /tmp/requirements-model.txt \
    && rm -f /tmp/requirements.txt /tmp/requirements-model.txt

COPY backend/ /app/backend/

RUN mkdir -p /app/runtime/models /app/runtime/logs \
    && chown -R baro:baro /app/backend /app/runtime

USER baro

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3).read()"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
