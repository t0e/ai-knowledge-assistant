# Acme Corp Employee Handbook & Workplace Guidelines

## 1. Annual Leave and Vacation Policy
Full-time permanent employees are entitled to 25 days of paid annual leave per calendar year. Up to 10 unused leave days may be rolled over into the subsequent calendar year, but must be utilized before March 31st.

## 2. Remote Work and Equipment Allowances
Acme Corp operates a remote-first workplace model. All eligible full-time staff receive a one-time home office equipment stipend of $1,000 USD upon joining, alongside a recurring monthly internet and mobile connectivity reimbursement of $75 USD.

## 3. Performance Reviews and Promotion Cycles
Performance evaluations are conducted on a quarterly cadence in March, June, September, and December. Annual salary adjustments and discretionary performance bonuses are determined during the Q4 review cycle based on key objective results (OKRs).
EOF && cat << 'EOF' > demo_data/cloud_architecture.md
# Acme Corp Cloud Architecture & API Specification

## 1. RESTful API Versioning
All core API endpoints are prefixed with `/api/v1`. The backend uses asynchronous request handlers with JSON payloads following standard HTTP status codes.

## 2. Asynchronous Job Processing with Redis ARQ
Heavy I/O and CPU workloads including document extraction, chunking, and embedding generation are processed asynchronously using Redis and the ARQ worker framework with up to 3 automatic retries.

## 3. Vector Storage and pgvector Indexing
Vector embeddings of 1536 dimensions are persisted directly inside PostgreSQL using the `pgvector` extension. Cosine similarity indexes enable fast top-k retrieval isolated by user.
