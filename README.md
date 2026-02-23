# Collaborative Markdown Editor

A full-stack real-time collaborative editor for Markdown and LaTeX, with a built-in NLP analytics dashboard and automatic version history.

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white" alt="Python 3.12">
  <img src="https://img.shields.io/badge/FastAPI-0.109-009688?logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white" alt="Docker">
  <img src="https://img.shields.io/badge/License-MIT-green" alt="MIT License">
</p>

<p align="center">
  A real-time collaborative Markdown editor with live LaTeX rendering, an NLP analytics dashboard, and PostgreSQL-backed version history — all running in Docker.
</p>

---

> Write together. Analyse deeply. Version everything.

Multiple users can edit the same document simultaneously with zero conflicts, powered by the [Yjs CRDT](https://yjs.dev/). A built-in analytics sidebar provides live NLP insights — readability, sentiment, topic modeling, named entities, and more — directly alongside the editor. Every edit is automatically snapshotted so you always have a full history to compare, restore, or diff.

---

## Features

| | |
|---|---|
| ⚡ **Real-time collaboration** | Conflict-free multi-user sync via Yjs CRDT. No operational transforms, no merge conflicts. |
| ✍️ **Monaco Editor** | The same editor engine as VS Code — syntax highlighting, keyboard shortcuts, and word wrap out of the box. |
| 🔢 **LaTeX math** | Inline `$...$` and display `$$...$$` equations rendered live via KaTeX. |
| 📊 **NLP analytics sidebar** | Live readability scoring, NER, sentiment, topic modeling, keyword extraction, and version comparison. |
| 🕒 **Full version history** | Automatic snapshots every 2 s of inactivity plus a background scheduler. SHA-256 deduplication, atomic numbering, restore on reconnect. |
| 📄 **Export** | Download as `.md` or generate a formatted A4 PDF client-side. One-click share link. |
| 🐳 **One-command setup** | `docker compose up --build -d` starts the full stack — PostgreSQL, backend, and frontend. |

---

## NLP Analytics Dashboard

The analytics sidebar sits alongside the editor and updates as you write. It is powered by **spaCy 3.7**, **scikit-learn 1.4**, and **TextBlob**, with all charts rendered by **Chart.js 4.4**.

### Metrics tab
Live word / character / sentence / paragraph counts and reading time. Flesch Reading Ease and Flesch-Kincaid Grade Level displayed with a colour-coded gauge. A line chart tracks readability across every saved version.

### Analysis tab
- **Named Entity Recognition** — spaCy NER groups people, organisations, locations, dates, and more by category with frequency counts
- **Sentiment** — TextBlob polarity (−1 → +1) and subjectivity (0 → 1) with visual progress bars
- **Topic modeling** — NMF or LDA with 2–10 configurable topics, rendered as a doughnut chart with ranked keyword cards
- **Keywords** — TF-IDF extraction with a horizontal bar chart
- **Vocabulary** — type-token ratio, lexical density, top content words
- **Sentence lengths** — histogram binned into 8 buckets
- **POS mix** — part-of-speech breakdown (top 8 tags)
- **Math content** — inline/block equation counts, math density, LaTeX structure detection

### Insights tab
Rolling word-growth line chart and editing-burst bar chart built from live session samples. Shows peak writing pace and net word change.

### Compare tab
Pick any two saved versions from dropdowns. View a colour-coded word-level diff (green = inserted, red = deleted) with a summary of total insertions, deletions, and changes. Metric delta cards show how readability, sentiment, and word count shifted between the two versions.

**Under the hood:** a two-tier cache (500-entry in-memory FIFO + PostgreSQL `document_analytics` keyed by SHA-256 content hash) means repeated analytics on unchanged content costs nothing. An 800 ms debounce with in-flight request cancellation keeps network usage low. Basic metrics always appear instantly client-side; server NLP enriches asynchronously.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| **Backend** | Python 3.12, FastAPI, python-socketio, Uvicorn |
| **Database** | PostgreSQL 16, asyncpg |
| **Real-time sync** | Yjs 13, y-websocket, y-monaco |
| **NLP / ML** | spaCy 3.7, TextBlob 0.18, scikit-learn 1.4 |
| **Charts** | Chart.js 4.4.1 |
| **Editor** | Monaco Editor 0.45.0 |
| **Markup / Math** | marked.js, KaTeX 0.16.9 |
| **Diff** | diff-match-patch 1.0.5 |
| **PDF export** | html2pdf.js |
| **Infrastructure** | Docker, Docker Compose |
| **Testing** | pytest, pytest-asyncio |

---

## Getting Started

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (includes Compose v2)

No local Python or PostgreSQL installation required — everything runs inside containers.

### Installation

```bash
git clone https://github.com/adabarbulescu/collaborative-latex-editor.git
cd collaborative-latex-editor
```

Create your environment file and set a database password:

```bash
cp .env.example .env
# Open .env and set POSTGRES_PASSWORD=yourpassword
```

Build and start all services:

```bash
docker compose up --build -d
```

Open **http://localhost:8000** in your browser. You will be redirected to a unique document URL (e.g. `/doc/a1b2c3d4`). PostgreSQL and the database schema are initialised automatically on first startup.

### First steps

1. Share the URL with collaborators — they join the live session instantly with no sign-up required
2. Write Markdown in the left pane; the rendered preview (with KaTeX math) updates in real time on the right
3. Use `$...$` for inline math and `$$...$$` for display equations
4. Click **Save Version** to create a manual snapshot, or let autosave handle it silently in the background
5. Open **Analytics** in the toolbar to explore NLP insights, topic modeling, and version comparisons

### Useful commands

```bash
docker compose logs -f          # tail logs from all services
docker compose down             # stop containers (data persists)
docker compose down -v          # stop containers and delete the database volume
docker compose restart backend  # restart only the backend after code changes
```



---

## API Reference

All endpoints are documented interactively at `/docs` (Swagger UI) when the server is running.

### Core

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Redirect to a new document |
| `GET` | `/doc/{id}` | Serve the editor frontend |
| `GET` | `/health` | Database connectivity check |
| `WS` | `/yjs/{room}` | Yjs WebSocket relay |

### Versioning
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/documents/{id}/versions` | Create a version snapshot |
| `GET` | `/api/documents/{id}/versions` | List all versions |
| `GET` | `/api/documents/{id}/versions/latest` | Get the latest version |
| `GET` | `/api/documents/{id}/versions/{n}` | Get version by number |

### Analytics
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/documents/{id}/analytics` | Full NLP analysis |
| `GET` | `/api/documents/{id}/insights` | Temporal insights from version history |
| `POST` | `/api/documents/{id}/topics` | Topic modeling (NMF / LDA) |
| `GET` | `/api/diff/{id}/versions` | List versions for comparison |
| `GET` | `/api/diff/{id}/compare?v1=&v2=` | Word-level diff + metric deltas |

### Admin / Monitoring
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/admin/scheduler/status` | Snapshot scheduler status |
| `GET` | `/api/admin/tracking/document/{id}` | Tracking stats for a document |
| `GET` | `/api/admin/tracking/all` | Tracking stats for all documents |
| `POST` | `/api/admin/tracking/snapshot/{id}` | Manually trigger a snapshot |

### Socket.IO Events

| Direction | Event | Purpose |
|-----------|-------|---------|
| Client → Server | `join_room` | Subscribe to a document room |
| Client → Server | `yjs_update` | Send a Yjs CRDT binary update |
| Client → Server | `awareness_update` | Broadcast cursor / presence state |
| Server → Client | `user_count` | Live connected-user count |
| Server → Client | `autosave` | Notification on auto-snapshot creation |
| Server → Client | `yjs_update` | Relay CRDT updates to peers |
| Server → Client | `awareness_update` | Relay cursor / presence to peers |

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|----------|
| `POSTGRES_USER` | Database user | `postgres` |
| `POSTGRES_PASSWORD` | Database password | *(required)* |
| `POSTGRES_DB` | Database name | `collab_editor` |
| `POSTGRES_HOST` | Database host | `db` |
| `POSTGRES_PORT` | Database port | `5432` |

---

## Project Structure

```
collaborative-latex-editor/
├── backend/
│   ├── main.py                # FastAPI application entry point
│   ├── config.py              # Pydantic settings
│   ├── database.py            # Async connection pool (asyncpg)
│   ├── init_db.py             # Schema initialisation
│   ├── models/                # Pydantic request/response schemas
│   │   ├── analytics.py
│   │   ├── diff.py
│   │   ├── document.py
│   │   └── topic.py
│   ├── routes/                # FastAPI routers
│   │   ├── analytics.py       # NLP analytics & topic endpoints
│   │   ├── diff.py            # Version comparison endpoints
│   │   ├── documents.py       # Document CRUD & frontend serving
│   │   ├── health.py
│   │   ├── monitoring.py      # Admin / scheduler endpoints
│   │   ├── versions.py        # Version history CRUD
│   │   └── websocket.py       # Yjs WebSocket relay
│   ├── services/              # Business logic
│   │   ├── analytics.py       # NLP computation & two-tier cache
│   │   ├── diff_service.py    # Word-level diff & analytics deltas
│   │   ├── nlp_pipeline.py    # spaCy model singleton
│   │   ├── topic_modeling.py  # NMF / LDA topic extraction
│   │   └── versioning.py      # Version snapshot service
│   ├── socket_handlers/
│   │   └── handlers.py        # Socket.IO event handlers
│   ├── tasks/
│   │   └── snapshot_scheduler.py  # Background autosave scheduler
│   ├── utils/                 # Yjs parsing, operation tracking
│   ├── tests/                 # pytest test suite
│   └── requirements.txt
├── frontend/
│   └── index.html             # Single-file frontend (editor + analytics)
├── docker-compose.yml
├── Dockerfile
└── README.md
```

---

## How It Works

### Conflict-free real-time editing
Every connected client holds a local [Yjs](https://yjs.dev/) CRDT document. Edits are encoded as compact binary updates and relayed through a Socket.IO server. Peers merge incoming updates locally — no central lock, no operational transform server, no conflicts.

### Version snapshots
A debounced autosave triggers 2 s after the last keystroke. A background scheduler runs every 60 s as a safety net, catching any document that has accumulated 50+ unsaved operations or 5+ minutes of activity since the last snapshot. Versions are stored in PostgreSQL with atomic sequential numbering and SHA-256 content-hash deduplication.

### NLP pipeline
spaCy's `en_core_web_sm` model is loaded once at startup via FastAPI's lifespan event and reused across all requests. Analytics results are cached in a two-tier store (process-local dict → PostgreSQL `document_analytics`) keyed by SHA-256 of the document content. Cache hits return in microseconds regardless of document size.

---

## Database Schema

### `documents`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | Auto-generated |
| title | VARCHAR(512) | Document title |
| owner_id | UUID | Owner reference |
| created_at | TIMESTAMPTZ | Creation timestamp |
| updated_at | TIMESTAMPTZ | Auto-updated on change |

### `document_versions`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | Auto-generated |
| document_id | UUID (FK) | References `documents.id` |
| content | TEXT | Document content snapshot |
| version_number | INTEGER | Sequential per document |
| created_at | TIMESTAMPTZ | Version timestamp |

### `document_analytics`
| Column | Type | Description |
|--------|------|-------------|
| id | UUID (PK) | Auto-generated |
| document_id | VARCHAR | Short document identifier |
| content_hash | VARCHAR (UNIQUE) | SHA-256 of document content (cache key) |
| analytics_data | JSONB | Full analytics result |
| computed_at | TIMESTAMPTZ | Computation timestamp |

---

## Accessibility & Responsive Design

- Full WAI-ARIA tab pattern — arrow-key navigation, Alt+A sidebar toggle, Escape to close
- `aria-live` regions on all metric cards, status indicators, and toast notifications
- `prefers-reduced-motion` respected — all CSS transitions and animations disabled when active
- Mobile-first layout with four breakpoints (1024 / 768 / 480 / 360 px)
- Dedicated Editor / Preview / Split toggle on mobile; analytics opens as a full-screen overlay
- 36 px minimum touch targets on all interactive controls

---

## Known Limitations

- **English only** — the spaCy model (`en_core_web_sm`) and TextBlob sentiment are trained on English text. Analytics results on other languages will be inaccurate.
- **Single-instance deployment** — the in-memory analytics cache and Socket.IO room state are process-local. Horizontal scaling requires a shared cache (e.g. Redis) and a sticky-session load balancer.
- **No authentication** — documents are accessible to anyone with the URL. All editors are anonymous.
- **Document size** — there is no hard size limit, but NLP analysis (NER, topic modeling) becomes slow above ~50 000 words due to synchronous spaCy processing.
- **PDF export** — generated client-side via html2pdf.js; complex LaTeX environments (tikz, custom macros) are not supported.
- **Browser support** — requires a modern browser with ES2020+ and WebSocket support. Internet Explorer is not supported.

---

## Contributing

Pull requests are welcome. For significant changes please open an issue first to discuss the approach.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m 'Add my feature'`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

### Code style

There is no enforced linter in CI, but please follow these conventions to keep the codebase consistent:

- **Python** — [PEP 8](https://peps.python.org/pep-0008/) formatting; [Black](https://black.readthedocs.io/) defaults (88-char line length) are a good target
- **Imports** — stdlib → third-party → local, separated by blank lines (isort-compatible)
- **Type hints** — add return types and parameter annotations for all new functions
- **JavaScript** — 2-space indentation, `const`/`let` only, no global state outside documented `window.*` assignments

To run the test suite:

```bash
docker compose exec backend pytest
```

---

## License

Distributed under the [MIT License](LICENSE).
