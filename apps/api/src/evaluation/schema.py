from typing import Any

from pydantic import BaseModel, Field


class EvalCase(BaseModel):
    """Ground truth evaluation test case schema."""

    id: str = Field(..., description="Unique test case identifier")
    category: str = Field(
        ...,
        description="Category: direct_factual | semantic_paraphrased | multi_source | follow_up | unanswerable | partially_answerable | website",
    )
    question: str = Field(..., description="The query to ask the RAG system")
    expected_answer: str | None = Field(
        None, description="Ground truth answer snippet or description"
    )
    expected_document: str | None = Field(None, description="Expected source document filename")
    expected_heading: str | None = Field(None, description="Expected section heading")
    expected_page: int | None = Field(None, description="Expected page number for PDFs")
    expected_url: str | None = Field(None, description="Expected source URL for website sources")
    expected_keywords: list[str] = Field(
        default_factory=list,
        description="Keywords that must appear in the retrieved context/answer",
    )
    answerable: bool = Field(
        True, description="Whether the question is answerable from the knowledge base"
    )
    notes: str | None = Field(None, description="Additional context or notes for the test case")
    history: list[dict[str, str]] | None = Field(
        None, description="Optional prior conversation turns for follow-up testing"
    )


class RetrievalResultItem(BaseModel):
    """Detailed retrieval metrics for a single question."""

    case_id: str
    category: str
    question: str
    expected_doc: str | None = None
    expected_heading: str | None = None
    expected_url: str | None = None
    answerable: bool = True
    retrieved_chunks: list[dict[str, Any]] = Field(default_factory=list)
    hit_at_1: bool = False
    hit_at_3: bool = False
    hit_at_5: bool = False
    rank: int | None = None
    reciprocal_rank: float = 0.0
    retrieval_latency_ms: float = 0.0
    failure_reason: str | None = None


class GenerationResultItem(BaseModel):
    """Detailed generation & citation metrics for a single question."""

    case_id: str
    category: str
    question: str
    answerable: bool = True
    generated_answer: str
    is_correct: bool = False
    is_refusal: bool = False
    correct_refusal: bool = False
    groundedness_score: int = Field(
        0,
        ge=0,
        le=4,
        description="0: unsupported, 1: mostly unsupported, 2: partially supported, 3: mostly supported, 4: fully supported",
    )
    groundedness_reason: str = ""
    total_citations: int = 0
    valid_citations_count: int = 0
    hallucinated_citations_count: int = 0
    citations: list[dict[str, Any]] = Field(default_factory=list)
    ttft_ms: float = 0.0
    generation_latency_ms: float = 0.0
    total_latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0


class RetrievalMetricsSummary(BaseModel):
    """Aggregated retrieval benchmark metrics."""

    total_questions: int
    answerable_questions: int
    hit_at_1_rate: float
    hit_at_3_rate: float
    hit_at_5_rate: float
    mrr: float
    avg_retrieval_latency_ms: float


class GenerationMetricsSummary(BaseModel):
    """Aggregated generation, citation, and operational benchmark metrics."""

    total_evaluated: int
    correctness_rate: float
    avg_groundedness: float
    unanswerable_total: int
    unanswerable_correctly_refused: int
    unanswerable_refusal_rate: float
    total_citations: int
    valid_citations_rate: float
    hallucinated_citations_count: int
    avg_ttft_ms: float
    avg_generation_latency_ms: float
    avg_total_latency_ms: float
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    total_estimated_cost_usd: float


class BenchmarkReport(BaseModel):
    """Complete machine-readable evaluation report."""

    timestamp: str
    mode: str
    config: dict[str, Any]
    retrieval_metrics: RetrievalMetricsSummary
    generation_metrics: GenerationMetricsSummary | None = None
    detailed_retrieval_results: list[RetrievalResultItem] = Field(default_factory=list)
    detailed_generation_results: list[GenerationResultItem] = Field(default_factory=list)
