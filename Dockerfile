# syntax=docker/dockerfile:1

# ---- Stage 1: build the React frontend ----
FROM node:20-slim AS frontend
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# ---- Stage 2: Python runtime ----
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
# Bring in the compiled UI from the build stage
COPY --from=frontend /app/dist ./dist
# Railway (and most hosts) inject $PORT; bind 0.0.0.0 so it's reachable
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
