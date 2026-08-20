# AI Knowledge Assistant

> Production-quality RAG (Retrieval-Augmented Generation) Platform for document intelligence, built with Next.js 15, FastAPI, PostgreSQL (pgvector), and Redis.

---

## 🌟 Overview

**AI Knowledge Assistant** is an enterprise-oriented AI assistant platform that enables users to upload PDF and Markdown documents, process them into chunked embeddings in the background, store vectors in PostgreSQL with `pgvector`, and ask questions through an interactive streaming chat interface with grounded citations.

### Phase 1: Foundation (Current Status)
- ✅ **Monorepo Structure**: Clean separation of frontend (`apps/web`) and backend (`apps/api`).
- ✅ **FastAPI 0.115+ Backend**: Fully asynchronous, Pydantic v2 schemas, OpenAPI v3 documentation, typed configuration, and RFC 7807 problem details error handling.
- ✅ **PostgreSQL 16 + pgvector**: Database container with HNSW vector indexing capability and Alembic migration pipeline.
- ✅ **Redis 7**: High-performance broker and caching tier.
- ✅ **Next.js 15 App Router Frontend**: TypeScript, Tailwind CSS, responsive Sidebar/Header shell, live backend health diagnostics badge, and placeholder views.
- ✅ **Docker Compose Orchestration**: Unified multi-container environment with inter-service networking and health probes.

---

## 🏗️ Architecture & Tech Stack

```
ai-knowledge-assistant/
├── apps/
│   ├── api/                   # FastAPI Backend
│   │   ├── alembic/           # Database migration versions
│   │   ├── src/
│   │   │   ├── api/           # API Routers & Versioned Endpoints (/api/v1)
│   │   │   ├── core/          # Settings, Database Engine, Redis, Exceptions
│   │   │   ├── models/        # SQLAlchemy ORM Models
│   │   │   └── schemas/       # Pydantic v2 Request/Response DTOs
│   │   └── tests/             # Pytest Unit & Integration Suite
│   └── web/                   # Next.js 15 App Router Frontend
│       ├── src/
│       │   ├── app/           # App routes: /, /documents, /chat
│       │   ├── components/    # Layout (Sidebar, Header) & UI Atoms
│       │   ├── lib/           # Typed API Client & Utilities
│       │   └── types/         # TypeScript Interfaces
└── docker-compose.yml         # Container Orchestration (Web, API, Postgres, Redis)
```

| Component | Technology | Description |
| :--- | :--- | :--- |
| **Frontend** | Next.js 15, React 19, TypeScript, Tailwind CSS | Modern dashboard shell with live health telemetry |
| **Backend API** | Python 3.12, FastAPI, Pydantic v2 | High-throughput asynchronous REST API |
| **Database** | PostgreSQL 16 + `pgvector` | Relational metadata + high-dimensional vector embeddings |
| **ORM & Migrations** | SQLAlchemy 2.0 (Async) + Alembic | Type-safe queries and schema versioning |
| **Cache & Queue** | Redis 7 Alpine | Background task broker and state management |
| **Containerization** | Docker & Docker Compose | Isolated multi-service development and production builds |

---

## 🚀 Quick Start with Docker Compose

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) (v24+)
- [Docker Compose](https://docs.docker.com/compose/) (v2+)

### 1. Clone & Setup Environment
```bash
cp .env.example .env
```

### 2. Start the Entire Stack
```bash
docker compose up --build -d
```

### 3. Service URLs & Ports
- **Frontend Dashboard**: [http://localhost:3000](http://localhost:3000)
- **FastAPI Backend**: [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **API Health Endpoint**: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)
- **PostgreSQL**: `localhost:5432` (`postgres` / `postgres` / `knowledge_db`)
- **Redis**: `localhost:6379`

---

## 🧪 Verification & Diagnostics

### 1. Check Container Health Status
```bash
docker compose ps
```

### 2. Verify Backend Health & pgvector
```bash
curl -s http://localhost:8000/api/v1/health | jq .
```
Expected output:
```json
{
  "status": "healthy",
  "project_name": "AI Knowledge Assistant",
  "version": "0.1.0",
  "environment": "development",
  "database": {
    "status": "healthy",
    "connected": true,
    "pgvector_installed": true
  },
  "redis": {
    "status": "healthy",
    "connected": true
  }
}
```

### 3. Verify pgvector in PostgreSQL directly
```bash
docker compose exec postgres psql -U postgres -d knowledge_db -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"
```

### 4. Verify Redis connectivity
```bash
docker compose exec redis redis-cli ping
# Expected: PONG
```

---

## 🛠️ Local Development (Without Docker)

### Backend Setup
```bash
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Run tests
pytest

# Start development server
uvicorn apps.api.src.main:app --reload --port 8000
```

### Frontend Setup
```bash
cd apps/web
npm install
npm run dev
```

---

## 🗺️ Implementation Roadmap
- [x] **Phase 1: Foundation** (Monorepo, Docker Compose, FastAPI, Next.js, Postgres+pgvector, Redis)
- [ ] **Phase 2: Ingestion & Workers** (PDF/Markdown/URL parsers, recursive chunking, OpenAI embeddings, Celery queue)
- [ ] **Phase 3: RAG Engine & Streaming Chat** (HNSW vector retrieval, prompt grounding, citations, SSE streaming)
- [ ] **Phase 4: Frontend UI/UX** (Drag-and-drop upload manager, streaming chat interface, citation popovers)
- [ ] **Phase 5: Production Readiness** (End-to-end tests, rate limiting, security audits, benchmarking)
