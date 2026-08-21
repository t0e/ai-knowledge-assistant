import re
from typing import Any

from apps.api.src.evaluation.schema import (
    GenerationMetricsSummary,
    GenerationResultItem,
    RetrievalMetricsSummary,
    RetrievalResultItem,
)

# Standard pricing estimates (OpenAI GPT-4o-mini & text-embedding-3-small as reference)
DEFAULT_PROMPT_TOKEN_RATE = 0.15 / 1_000_000  # $0.15 per 1M tokens
DEFAULT_COMPLETION_TOKEN_RATE = 0.60 / 1_000_000  # $0.60 per 1M tokens
DEFAULT_EMBEDDING_TOKEN_RATE = 0.02 / 1_000_000  # $0.02 per 1M tokens

REFUSAL_PHRASES = [
    "couldn't find enough information",
    "could not find enough information",
    "does not contain enough information",
    "not mentioned in the provided",
    "not mentioned in the context",
    "not found in your uploaded documents",
    "not provided in the documents",
    "information is not available",
]


def match_chunk_to_ground_truth(
    chunk: dict[str, Any],
    expected_doc: str | None,
    expected_heading: str | None,
    expected_url: str | None,
    expected_keywords: list[str],
) -> bool:
    """Determine if a retrieved chunk matches ground truth expectations."""
    meta = chunk.get("metadata", {}) or {}
    doc_name = (chunk.get("document_name") or meta.get("original_filename") or "").lower()
    chunk_url = (chunk.get("source_url") or meta.get("url") or "").lower()
    chunk_heading = (meta.get("heading") or "").lower()
    content = (chunk.get("content") or "").lower()

    # 1. Document / URL matching
    doc_match = False
    if expected_url and (expected_url.lower() in chunk_url or expected_url.lower() in doc_name):
        doc_match = True
    elif expected_doc:
        doc_stem = expected_doc.split(".")[0].lower()
        if (
            expected_doc.lower() in doc_name
            or doc_stem in doc_name
            or doc_stem.replace("_", " ") in doc_name
            or "architecture" in doc_name
            and "architecture" in expected_doc.lower()
            or "handbook" in doc_name
            and "handbook" in expected_doc.lower()
            or "security" in doc_name
            and "security" in expected_doc.lower()
        ):
            doc_match = True
    else:
        doc_match = True

    if not doc_match:
        return False

    # 2. Heading / Keyword matching
    heading_match = False
    if expected_heading:
        h_lower = expected_heading.lower()
        if h_lower in chunk_heading or h_lower in content:
            heading_match = True
        # Check partial heading words
        h_words = [w for w in h_lower.split() if len(w) > 3]
        if (
            h_words
            and sum(1 for w in h_words if w in chunk_heading or w in content) >= len(h_words) // 2
        ):
            heading_match = True
    else:
        heading_match = True

    keyword_match = False
    if expected_keywords:
        kw_hits = sum(1 for kw in expected_keywords if kw.lower() in content)
        keyword_match = kw_hits >= max(1, len(expected_keywords) // 2)
    else:
        keyword_match = True

    return doc_match and (heading_match or keyword_match)


def compute_retrieval_hit(
    retrieved_chunks: list[dict[str, Any]],
    expected_doc: str | None,
    expected_heading: str | None,
    expected_url: str | None,
    expected_keywords: list[str],
    top_k: int = 5,
) -> tuple[bool, bool, bool, int | None, float, str | None]:
    """Calculate Hit@1, Hit@3, Hit@5, Rank, and Reciprocal Rank."""
    rank = None
    for idx, chunk in enumerate(retrieved_chunks[:top_k], start=1):
        if match_chunk_to_ground_truth(
            chunk, expected_doc, expected_heading, expected_url, expected_keywords
        ):
            rank = idx
            break

    if rank is not None:
        hit_at_1 = rank == 1
        hit_at_3 = rank <= 3
        hit_at_5 = rank <= 5
        reciprocal_rank = 1.0 / rank
        failure_reason = None
    else:
        hit_at_1 = False
        hit_at_3 = False
        hit_at_5 = False
        reciprocal_rank = 0.0
        failure_reason = f"Expected '{expected_doc or expected_url}' (heading: '{expected_heading}') not found in Top {top_k}"

    return hit_at_1, hit_at_3, hit_at_5, rank, reciprocal_rank, failure_reason


def calculate_retrieval_metrics(results: list[RetrievalResultItem]) -> RetrievalMetricsSummary:
    """Aggregate retrieval metrics over answerable evaluation items."""
    answerable_items = [r for r in results if r.answerable]
    total_q = len(results)
    ans_q = len(answerable_items)

    if ans_q == 0:
        return RetrievalMetricsSummary(
            total_questions=total_q,
            answerable_questions=0,
            hit_at_1_rate=0.0,
            hit_at_3_rate=0.0,
            hit_at_5_rate=0.0,
            mrr=0.0,
            avg_retrieval_latency_ms=0.0,
        )

    hit_1 = sum(1 for r in answerable_items if r.hit_at_1) / ans_q
    hit_3 = sum(1 for r in answerable_items if r.hit_at_3) / ans_q
    hit_5 = sum(1 for r in answerable_items if r.hit_at_5) / ans_q
    mrr = sum(r.reciprocal_rank for r in answerable_items) / ans_q
    avg_lat = sum(r.retrieval_latency_ms for r in results) / total_q if total_q > 0 else 0.0

    return RetrievalMetricsSummary(
        total_questions=total_q,
        answerable_questions=ans_q,
        hit_at_1_rate=round(hit_1 * 100, 2),
        hit_at_3_rate=round(hit_3 * 100, 2),
        hit_at_5_rate=round(hit_5 * 100, 2),
        mrr=round(mrr, 4),
        avg_retrieval_latency_ms=round(avg_lat, 2),
    )


def evaluate_answer_correctness(
    generated_text: str,
    expected_answer: str | None,
    expected_keywords: list[str],
    answerable: bool,
) -> tuple[bool, bool, bool]:
    """Evaluate whether answer is correct, refusal, and correct refusal."""
    text_lower = generated_text.lower()
    is_refusal = any(phrase in text_lower for phrase in REFUSAL_PHRASES)

    if not answerable:
        # For unanswerable questions, correct behavior is proper refusal!
        correct_refusal = is_refusal
        is_correct = is_refusal
        return is_correct, is_refusal, correct_refusal

    correct_refusal = False
    if is_refusal:
        # Answerable question was refused incorrectly
        return False, True, False

    # Check keyword presence
    if expected_keywords:
        matches = sum(1 for kw in expected_keywords if kw.lower() in text_lower)
        is_correct = matches >= max(1, len(expected_keywords) // 2)
    elif expected_answer:
        # Fallback to key terms from expected answer
        key_terms = [t for t in re.findall(r"\w+", expected_answer.lower()) if len(t) > 3]
        matches = sum(1 for term in key_terms if term in text_lower)
        is_correct = matches >= max(1, len(key_terms) // 2)
    else:
        is_correct = len(generated_text.strip()) > 10

    return is_correct, is_refusal, correct_refusal


def evaluate_groundedness(
    generated_text: str,
    context_text: str,
) -> tuple[int, str]:
    """
    Evaluate groundedness on a 0-4 rubric:
    0: Unsupported / Hallucinated
    1: Mostly unsupported
    2: Partially supported
    3: Mostly supported
    4: Fully supported
    """
    if not context_text:
        is_refusal = any(phrase in generated_text.lower() for phrase in REFUSAL_PHRASES)
        if is_refusal:
            return 4, "Refusal correctly handled with zero context."
        return 0, "Response generated claim without any supporting context."

    # Extract non-stopword tokens from generated answer
    words = re.findall(r"\b[A-Za-z0-9_]{3,}\b", generated_text.lower())
    if not words:
        return 4, "Trivial response."

    context_lower = context_text.lower()
    grounded_words = sum(1 for w in words if w in context_lower)
    overlap_ratio = grounded_words / len(words)

    if overlap_ratio >= 0.80:
        score = 4
        reason = f"Fully supported: {overlap_ratio * 100:.1f}% word overlap with context."
    elif overlap_ratio >= 0.65:
        score = 3
        reason = f"Mostly supported: {overlap_ratio * 100:.1f}% word overlap with context."
    elif overlap_ratio >= 0.45:
        score = 2
        reason = f"Partially supported: {overlap_ratio * 100:.1f}% word overlap with context."
    elif overlap_ratio >= 0.25:
        score = 1
        reason = f"Mostly unsupported: only {overlap_ratio * 100:.1f}% word overlap with context."
    else:
        score = 0
        reason = f"Unsupported/hallucinated: {overlap_ratio * 100:.1f}% word overlap with context."

    return score, reason


def validate_citations(
    citations: list[dict[str, Any]],
    retrieved_chunk_ids: set[str],
    expected_doc: str | None,
    expected_url: str | None,
) -> tuple[int, int]:
    """Return (valid_citations_count, hallucinated_citations_count)."""
    valid = 0
    hallucinated = 0

    for cit in citations:
        chunk_id = cit.get("chunk_id")
        # Check if chunk ID exists in retrieved chunks
        if chunk_id and str(chunk_id) in retrieved_chunk_ids:
            valid += 1
        elif cit.get("source_id") is not None and cit.get("document_name"):
            # Citation came through RAG context builder
            valid += 1
        else:
            hallucinated += 1

    return valid, hallucinated


def estimate_cost(prompt_tokens: int, completion_tokens: int, embedding_tokens: int = 0) -> float:
    """Calculate approximate USD cost based on token counts."""
    cost = (
        (prompt_tokens * DEFAULT_PROMPT_TOKEN_RATE)
        + (completion_tokens * DEFAULT_COMPLETION_TOKEN_RATE)
        + (embedding_tokens * DEFAULT_EMBEDDING_TOKEN_RATE)
    )
    return round(cost, 6)


def calculate_generation_metrics(results: list[GenerationResultItem]) -> GenerationMetricsSummary:
    """Aggregate generation and citation metrics."""
    total = len(results)
    if total == 0:
        return GenerationMetricsSummary(
            total_evaluated=0,
            correctness_rate=0.0,
            avg_groundedness=0.0,
            unanswerable_total=0,
            unanswerable_correctly_refused=0,
            unanswerable_refusal_rate=0.0,
            total_citations=0,
            valid_citations_rate=0.0,
            hallucinated_citations_count=0,
            avg_ttft_ms=0.0,
            avg_generation_latency_ms=0.0,
            avg_total_latency_ms=0.0,
            total_prompt_tokens=0,
            total_completion_tokens=0,
            total_tokens=0,
            total_estimated_cost_usd=0.0,
        )

    correct = sum(1 for r in results if r.is_correct)
    avg_groundedness = sum(r.groundedness_score for r in results) / total

    unans = [r for r in results if not r.answerable]
    unans_total = len(unans)
    unans_refused = sum(1 for r in unans if r.correct_refusal)
    unans_rate = (unans_refused / unans_total * 100) if unans_total > 0 else 100.0

    total_cit = sum(r.total_citations for r in results)
    valid_cit = sum(r.valid_citations_count for r in results)
    halluc_cit = sum(r.hallucinated_citations_count for r in results)
    valid_cit_rate = (valid_cit / total_cit * 100) if total_cit > 0 else 100.0

    avg_ttft = sum(r.ttft_ms for r in results) / total
    avg_gen_lat = sum(r.generation_latency_ms for r in results) / total
    avg_tot_lat = sum(r.total_latency_ms for r in results) / total

    prompt_tok = sum(r.prompt_tokens for r in results)
    comp_tok = sum(r.completion_tokens for r in results)
    tot_tok = sum(r.total_tokens for r in results)
    cost = sum(r.estimated_cost_usd for r in results)

    return GenerationMetricsSummary(
        total_evaluated=total,
        correctness_rate=round((correct / total) * 100, 2),
        avg_groundedness=round(avg_groundedness, 2),
        unanswerable_total=unans_total,
        unanswerable_correctly_refused=unans_refused,
        unanswerable_refusal_rate=round(unans_rate, 2),
        total_citations=total_cit,
        valid_citations_rate=round(valid_cit_rate, 2),
        hallucinated_citations_count=halluc_cit,
        avg_ttft_ms=round(avg_ttft, 2),
        avg_generation_latency_ms=round(avg_gen_lat, 2),
        avg_total_latency_ms=round(avg_tot_lat, 2),
        total_prompt_tokens=prompt_tok,
        total_completion_tokens=comp_tok,
        total_tokens=tot_tok,
        total_estimated_cost_usd=round(cost, 6),
    )
