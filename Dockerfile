# Satu container untuk Cloud Run: FastAPI menyajikan API + frontend/dist.

# --- Stage 1: build frontend ---
# ponytail: Node 22 (bukan 20) karena Node 20 sudah EOL dan Vite 8 butuh >=20.19
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Stage 2: backend Python + uv ---
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
# opencv (dependensi rapidocr) butuh libGL + glib
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy \
    PATH="/app/backend/.venv/bin:$PATH" \
    OMNI_DATA=/tmp/data PYTHONUNBUFFERED=1

WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
RUN uv sync --frozen --no-dev

COPY demo/ /app/demo/
COPY --from=web /web/dist /app/frontend/dist

# Seed (termasuk OCR PDF scan) dijalankan saat build, bukan saat cold start.
# Tanpa GEMINI_API_KEY saat build -> ekstraksi pola teks lokal.
# Path di DB absolut (/tmp/data/...), jadi hasil seed disimpan lalu disalin balik ke /tmp/data saat start.
RUN python -m app.seed && mv /tmp/data /app/seed-data

ENV PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "[ -f /tmp/data/omniaudit.db ] || cp -r /app/seed-data /tmp/data; exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
