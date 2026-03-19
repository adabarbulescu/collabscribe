FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend-app

COPY frontend-app/package.json ./
RUN npm install

COPY frontend-app/ ./
RUN npm run build

FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies required by asyncpg
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc libpq-dev && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (layer caching)
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy model (pip install is more reliable than spacy download)
RUN pip install --no-cache-dir https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl

# Download NLTK corpora at build time (no internet at runtime)
RUN python -c "import nltk; nltk.download('punkt_tab', quiet=True); nltk.download('averaged_perceptron_tagger', quiet=True); nltk.download('brown', quiet=True)"

# Copy application code
COPY backend/ ./backend/
COPY --from=frontend-build /app/frontend-app/dist ./frontend-app/dist
COPY frontend-app/package.json ./frontend-app/package.json

WORKDIR /app/backend

EXPOSE 8000

CMD ["uvicorn", "main:combined_app", "--host", "0.0.0.0", "--port", "8000"]
