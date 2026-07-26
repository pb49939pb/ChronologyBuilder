# Build with the REPO ROOT as context (not webapp/), since app.py also needs the sibling
# prompts/ directory — see docker-compose.yml's `build.context: .` at the repo root.
#
# Recommended for the eventual Linux/NVIDIA production workstation (PRODUCT_DEFINITION.md §4/§6),
# NOT for an Apple Silicon Mac: Docker Desktop on macOS cannot pass the Metal GPU through to a
# container as of 2026 (confirmed still true even on current-generation hardware), so Ollama would
# fall back to CPU-only inference, ~3-5x slower. On Apple Silicon, run Ollama natively (as this
# project already does via a LaunchAgent) and skip the ollama container in docker-compose.yml —
# this webapp container can still point at the native instance via LAWFIRMAGENT_OLLAMA_URL.
FROM python:3.11-slim

WORKDIR /app

COPY webapp/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY webapp/app.py .
COPY webapp/static/ static/
COPY webapp/templates/ templates/
COPY prompts/ /prompts/

ENV LAWFIRMAGENT_BIND_HOST=0.0.0.0
EXPOSE 5050

CMD ["python", "app.py"]
