# ── Stage 1: Build frontend ───────────────────────────────────────────────────
FROM node:20-slim AS frontend-build
WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./

# Empty VITE_API_BASE = relative URLs so frontend calls /sessions etc.
# on the same origin as the backend
ENV VITE_API_BASE=
RUN npm run build

# ── Stage 2: Production image ─────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

COPY backend/pyproject.toml ./
RUN pip install --no-cache-dir fastapi uvicorn[standard] sqlalchemy python-dotenv pydantic

COPY backend/app ./app

# Copy built frontend (served as static files by FastAPI)
COPY --from=frontend-build /frontend/dist ./frontend/dist

# Persistent data directory (mount a Fly volume here)
RUN mkdir -p /data

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
