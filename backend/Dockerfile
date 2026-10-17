FROM python:3.11-slim@sha256:da047cb8f9d1d98e5c070f5300ba9f7274e33b8fc0e5be5ed88740aed1b95ba9
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 FASTEMBED_CACHE_PATH=/tmp/fastembed HF_HOME=/tmp/huggingface
WORKDIR /app
COPY backend /app/backend
COPY data /app/data
RUN pip install --no-cache-dir pip==26.2.1 setuptools==83.0.0 wheel==0.46.2 && pip install --no-cache-dir --require-hashes -r backend/requirements-runtime.lock && pip install --no-cache-dir --no-deps --no-build-isolation './backend[local]' && useradd --create-home --uid 10001 sai
USER sai
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/api/v1/health',timeout=3)"
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips=''"]
