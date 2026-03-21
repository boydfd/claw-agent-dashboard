# Build args for registry mirrors (override at build time for proxies)
ARG NPM_REGISTRY=https://registry.npmjs.org/
ARG PIP_INDEX_URL=https://pypi.org/simple/

# Stage 1: Build frontend
FROM node:20-alpine AS frontend-build
ARG NPM_REGISTRY
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm config set registry ${NPM_REGISTRY}
RUN npm install
COPY frontend/ .
RUN npm run build

# Stage 2: Python runtime
FROM python:3.12-slim
ARG PIP_INDEX_URL
WORKDIR /app

# Create a non-root user with uid=1000 to match the typical host user.
# This ensures files written to bind-mounted host directories (e.g. /agents)
# are owned by uid=1000 rather than root.
RUN groupadd -g 1000 appuser && useradd -u 1000 -g 1000 -m appuser

# Install Python dependencies
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -i ${PIP_INDEX_URL} -r backend/requirements.txt

# Copy backend code
COPY backend/ ./backend/

# Copy frontend build
COPY --from=frontend-build /app/frontend/dist ./static/

# Create data directory and transfer ownership
RUN mkdir -p /data/agents && chown -R appuser:appuser /app /data

USER appuser

EXPOSE 8080

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
