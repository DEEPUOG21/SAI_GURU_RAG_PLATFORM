FROM cgr.dev/chainguard/wolfi-base@sha256:88a20e2d017bd20cdc0cb3910de603e7bea9512a6c351a8dd3c9df212ab03d73
RUN apk upgrade --no-cache && apk add --no-cache python-3.11 libstdc++ libgomp && python3.11 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 FASTEMBED_CACHE_PATH=/tmp/fastembed HF_HOME=/tmp/huggingface
WORKDIR /app
ENV SAI_DATA_DIR=/app/data
COPY backend /app/backend
COPY data /app/data
RUN pip install --no-cache-dir pip==26.2.1 setuptools==83.0.0 wheel==0.46.2 && pip install --no-cache-dir --require-hashes -r backend/requirements-runtime.lock && pip install --no-cache-dir --no-deps --no-build-isolation './backend[local]' && adduser -D -u 10001 sai
# Build tools are not runtime dependencies; their vendored packages also carry advisories.
RUN python -m pip uninstall --yes pip setuptools wheel && python -c "from fastembed import TextEmbedding; from fastembed.rerank.cross_encoder import TextCrossEncoder; import app.main"
USER sai
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8000')+'/api/v1/health',timeout=3)"
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips=''"]
