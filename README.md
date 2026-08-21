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

---

## 📊 RAG Evaluation & Observability (Phase 9)

The platform includes a dedicated, lightweight evaluation and observability framework to benchmark and measure RAG performance deterministically.

### 🎯 Evaluation Metric Dimensions
```text
Evaluation Dataset (25 cases across 7 categories)
       ↓
┌─────────────────────────────────────────────────────────────┐
│ 1. Retrieval Metrics                                        │
│    • Hit@1, Hit@3, Hit@5 (% expected chunk in top-K)        │
│    • MRR (Mean Reciprocal Rank)                             │
│    • Retrieval Latency (ms)                                 │
├─────────────────────────────────────────────────────────────┤
│ 2. Generation & Groundedness Metrics                        │
│    • Answer Correctness (% deterministic key fact match)    │
│    • Groundedness Rubric (0: Hallucinated → 4: Fully Valid) │
│    • Unanswerable Refusal Rate (% correctly refused)        │
├─────────────────────────────────────────────────────────────┤
│ 3. Citation Quality & Anti-Hallucination                    │
│    • Citation Validity (% matching retrieved chunks)        │
│    • Hallucinated Citation Count (Strict target = 0)        │
├─────────────────────────────────────────────────────────────┤
│ 4. Operational Latency & Token Usage                        │
│    • Time to First Token (TTFT)                             │
│    • Generation Latency & Total Request Duration            │
│    • Prompt & Completion Tokens, Cost Estimation (USD)      │
└─────────────────────────────────────────────────────────────┘
       ↓
Machine-Readable Artifacts (`evaluation/results/eval_*.json`) + CLI Summary
```

### ⚡ Running Evaluation

#### 1. Retrieval-Only Mode (Fast & Offline — No paid LLM calls)
```bash
docker compose exec backend python3 -m apps.api.src.evaluation.cli --mode retrieval --top-k 5
```

#### 2. Full End-to-End RAG Evaluation (Generation, Groundedness, Citations, Latency)
```bash
docker compose exec backend python3 -m apps.api.src.evaluation.cli --mode full --top-k 5
```

---

## 🗺️ Implementation Roadmap
- [x] **Phase 1: Foundation** (Monorepo, Docker Compose, FastAPI, Next.js, Postgres+pgvector, Redis)
- [x] **Phase 2: Authentication & Multi-Tenancy** (JWT Cookies, Argon2/Bcrypt hashing, User isolation)
- [x] **Phase 3: Document Management & Storage** (PDF/Markdown uploads, metadata storage, deduplication)
- [x] **Phase 4: Document Processing & Chunking** (PDF text extraction, Recursive chunker, token windowing)
- [x] **Phase 5: Embeddings & Vector Search** (OpenAI embeddings, pgvector cosine distance similarity)
- [x] **Phase 6: Conversational RAG & Streaming** (SSE streaming, grounded context builder, citations, multi-turn history)
- [x] **Phase 7: Redis Background Processing** (ARQ workers, async polling, retry backoff, queue monitoring)
- [x] **Phase 8: Website / URL Ingestion** (SSRF defense in depth, DNS validation, HTML extraction, noise filtering)
- [x] **Phase 9: RAG Evaluation & Observability** (Hit@K, MRR, Groundedness, TTFT latency, request correlation IDs)

