FROM python:3.11-slim@sha256:673719e071ecf27434fd2635bbd8d00f49f4fdd81f243143438a42ced8bedf60
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 FASTEMBED_CACHE_PATH=/tmp/fastembed HF_HOME=/tmp/huggingface
WORKDIR /app
ENV SAI_DATA_DIR=/app/data
COPY backend /app/backend
COPY data /app/data
RUN pip install --no-cache-dir pip==26.2.1 setuptools==83.0.0 wheel==0.46.2 && pip install --no-cache-dir --require-hashes -r backend/requirements-runtime.lock && pip install --no-cache-dir --no-deps --no-build-isolation './backend[local]' && useradd --create-home --uid 10001 sai
# Build tools are not runtime dependencies; their vendored packages also carry advisories.
RUN python -m pip uninstall --yes pip setuptools wheel && python -c "from fastembed import TextEmbedding; from fastembed.rerank.cross_encoder import TextCrossEncoder; import app.main"
USER sai
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/api/v1/health',timeout=3)"
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips=''"]
