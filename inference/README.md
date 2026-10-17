---
title: Sai Guru Private Inference
emoji: 📚
colorFrom: green
colorTo: gray
sdk: docker
app_port: 7860
---

Optional CPU model host for Sai Guru. Set the `INFERENCE_API_KEY` Space secret before startup. Model endpoints require that key. Never place it in React.

Copy `inference/Dockerfile` to the root `Dockerfile` of the Space repository while preserving the `inference/` directory containing its referenced files. See the main project's deployment guide.

Model downloads default to revision `7dabda4d13d513e3e842b20f0d435c732f172cbe`. When changing `MODEL_REPO` or `MODEL_FILE`, also set `MODEL_REVISION` to an audited immutable commit for that repository. `MODEL_PATH` bypasses downloading and must point to a trusted local GGUF. Other optional service variables are `PORT` (7860), `MODEL_THREADS` (2), `HF_HOME` and `FASTEMBED_CACHE_PATH` (cache directories). Disk prompt caching is explicitly disabled. This limits exposure to the diskcache pickle advisory; the vulnerable transitive package remains installed.

The default Qwen2.5-3B-Instruct Q4_K_M model is a CPU portfolio option (approximately 2.1 GB of weights, plus runtime memory). It replaces the 1.5B model after multi-turn tests exposed weak instruction following. It can still produce incorrect answers and grounding judgments. Select another compatible GGUF with `MODEL_REPO` and `MODEL_FILE`; `MODEL_THREADS` defaults to 2 on the service and 4 in the local launcher. Check memory, latency, license and hosting limits first. The weights use the upstream [Qwen Research license](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/blob/main/LICENSE), separately from this application's MIT license.
