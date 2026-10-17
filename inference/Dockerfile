FROM python:3.11-slim@sha256:da047cb8f9d1d98e5c070f5300ba9f7274e33b8fc0e5be5ed88740aed1b95ba9
RUN useradd --create-home --uid 1000 user
WORKDIR /app
COPY inference/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir pip==26.2.1 setuptools==83.0.0 wheel==0.46.2 && pip install --no-cache-dir -r requirements.txt --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu --only-binary llama-cpp-python
COPY inference/server.py /app/server.py
ENV HF_HOME=/tmp/huggingface FASTEMBED_CACHE_PATH=/tmp/fastembed PORT=7860
USER user
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=300s CMD python -c "import os,urllib.request; r=urllib.request.Request('http://127.0.0.1:'+os.getenv('PORT','7860')+'/v1/models',headers={'Authorization':'Bearer '+os.environ['INFERENCE_API_KEY']}); urllib.request.urlopen(r,timeout=3)"
CMD ["python", "server.py"]
