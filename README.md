# Collabscribe

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white" alt="Python 3.12">
  <img src="https://img.shields.io/badge/FastAPI-0.109-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/React-18-20232A?logo=react&logoColor=61DAFB" alt="React 18">
  <img src="https://img.shields.io/badge/Vite-5-646CFF?logo=vite&logoColor=white" alt="Vite 5">
  <img src="https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white" alt="Docker Compose">
</p>

Collabscribe is a real-time collaborative Markdown editor with live math rendering, version history, and built-in NLP analytics.

## Highlights

- Real-time collaborative editing with Yjs
- Markdown preview with KaTeX math support
- Saved document versions with diff comparison
- NLP analytics for readability, sentiment, entities, keywords, vocabulary, and topics
- FastAPI backend with PostgreSQL persistence
- React + Vite frontend with Monaco Editor
- Docker-based local setup

## Stack

- Python 3.12
- FastAPI
- React + Vite
- PostgreSQL
- Socket.IO
- Yjs
- Monaco Editor
- spaCy, TextBlob, scikit-learn
- Docker Compose

## Run Locally

```bash
git clone https://github.com/adabarbulescu/collabscribe.git
cd collabscribe
cp .env.example .env
docker compose up --build -d
```

Open `http://localhost:8000`.

For frontend-only development:

```bash
cd frontend-app
npm install
npm run dev
```

## Testing

```bash
pytest backend/tests -q
```

- Yjs and snapshot unit tests run locally.
- Versioning tests require a local PostgreSQL test database at `postgresql://postgres:postgres@localhost:5432/collabscribe_test`.
- If that database is unavailable, those tests are skipped.
- Docker builds the React frontend and serves the compiled app through FastAPI.

## Notes

- Analytics are currently tuned for English text.
- API docs are available at `/docs` when the app is running.
