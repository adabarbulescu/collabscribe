# Collabscribe

Collabscribe is a real-time collaborative Markdown editor with live math rendering, version history, and built-in NLP analytics.

It is designed as a portfolio project that combines real-time systems, backend API design, persistence, and text-analysis features in one product.

## Highlights

- Real-time collaborative editing with Yjs
- Markdown preview with KaTeX math support
- Saved document versions with diff comparison
- NLP analytics for readability, sentiment, entities, keywords, vocabulary, and topics
- FastAPI backend with PostgreSQL persistence
- Docker-based local setup

## Stack

- Python 3.12
- FastAPI
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

## Environment

The repo includes `.env.example` with the required database and app settings.

## Testing

```bash
pytest backend/tests -q
```

- Yjs and snapshot unit tests run locally.
- Versioning tests require a local PostgreSQL test database at `postgresql://postgres:postgres@localhost:5432/collabscribe_test`.
- If that database is unavailable, those tests are skipped.

## Project Structure

```text
.
|-- backend
|-- frontend
|-- docker-compose.yml
|-- Dockerfile
`-- README.md
```

## Notes

- Analytics are currently tuned for English text.
- The frontend is implemented as a single large HTML file.
- API docs are available at `/docs` when the app is running.
