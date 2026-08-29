FROM python:3.13-slim

# Unbuffered stdout/stderr so `render logs` streams immediately; no .pyc writes
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /srv

# Dependencies first (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code only — .dockerignore keeps db files/secrets/pycache out of the image
COPY app ./app

# Run as non-root (Render best practice)
RUN adduser --disabled-password --gecos "" --uid 1001 socialos \
    && chown -R socialos:socialos /srv
USER socialos

# Render injects $PORT (default 10000); local runs default to 8000
ENV SOCIALOS_AUTO_SEED=true
EXPOSE 8000

# sh -c is required for ${PORT} env expansion
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
