import datetime
import logging
import time
import uuid
from pathlib import Path
from typing import Any

from apps.api.src.core.config import settings
from apps.api.src.evaluation.metrics import (
    calculate_generation_metrics,
    calculate_retrieval_metrics,
    compute_retrieval_hit,
    estimate_cost,
    evaluate_answer_correctness,
    evaluate_groundedness,
    validate_citations,
)
from apps.api.src.evaluation.schema import (
    BenchmarkReport,
    EvalCase,
    GenerationResultItem,
    RetrievalResultItem,
)
from apps.api.src.llm.base import ChatMessage
from apps.api.src.llm.service import LLMService, get_llm_service
from apps.api.src.services.rag_service import SYSTEM_RAG_PROMPT, ContextBuilder
from apps.api.src.services.search_service import SemanticSearchService
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("ai_knowledge_assistant.evaluation.runner")
RESULTS_DIR = (
    Path("/app/apps/api/evaluation/results")
    if Path("/app/apps/api/evaluation/results").exists()
    else Path(__file__).parents[2] / "evaluation" / "results"
)


class EvaluationRunner:
    """Orchestrates retrieval and full RAG pipeline evaluation across benchmark test cases."""

    def __init__(
        self,
        search_service: SemanticSearchService | None = None,
        llm_service: LLMService | None = None,
    ):
        self.search = search_service or SemanticSearchService()
        self.llm = llm_service or get_llm_service()

    async def evaluate_retrieval_only(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        cases: list[EvalCase],
        top_k: int = 5,
    ) -> tuple[list[RetrievalResultItem], Any]:
        """Evaluate retrieval across all benchmark questions without calling paid LLMs."""
        retrieval_results: list[RetrievalResultItem] = []

        for case in cases:
            t0 = time.perf_counter()
            retrieved = await self.search.search(
                db=db,
                user_id=user_id,
                query=case.question,
                top_k=top_k,
            )
            lat_ms = (time.perf_counter() - t0) * 1000

            chunks_data = [
                {
                    "chunk_id": str(item.chunk_id),
                    "document_id": str(item.document_id),
                    "document_name": item.document_name,
                    "original_filename": item.original_filename,
                    "source_url": item.source_url,
                    "content": item.content,
                    "score": round(item.score, 4),
                    "metadata": item.metadata,
                }
                for item in retrieved
            ]

            if case.answerable:
                hit_1, hit_3, hit_5, rank, mrr, failure_reason = compute_retrieval_hit(
                    retrieved_chunks=chunks_data,
                    expected_doc=case.expected_document,
                    expected_heading=case.expected_heading,
                    expected_url=case.expected_url,
                    expected_keywords=case.expected_keywords,
                    top_k=top_k,
                )
            else:
                hit_1, hit_3, hit_5, rank, mrr, failure_reason = (
                    False,
                    False,
                    False,
                    None,
                    0.0,
                    None,
                )

            retrieval_results.append(
                RetrievalResultItem(
                    case_id=case.id,
                    category=case.category,
                    question=case.question,
                    expected_doc=case.expected_document,
                    expected_heading=case.expected_heading,
                    expected_url=case.expected_url,
                    answerable=case.answerable,
                    retrieved_chunks=chunks_data,
                    hit_at_1=hit_1,
                    hit_at_3=hit_3,
                    hit_at_5=hit_5,
                    rank=rank,
                    reciprocal_rank=mrr,
                    retrieval_latency_ms=round(lat_ms, 2),
                    failure_reason=failure_reason,
                )
            )

        summary = calculate_retrieval_metrics(retrieval_results)
        return retrieval_results, summary

    async def evaluate_full_rag(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        cases: list[EvalCase],
        top_k: int = 5,
    ) -> BenchmarkReport:
        """Execute full end-to-end evaluation including retrieval, generation, groundedness, and citations."""
        retrieval_items, retrieval_summary = await self.evaluate_retrieval_only(
            db=db, user_id=user_id, cases=cases, top_k=top_k
        )

        generation_items: list[GenerationResultItem] = []

        for case, ret_item in zip(cases, retrieval_items, strict=True):
            # 1. Build context and citations
            context_str, citations = ContextBuilder.build_context(
                chunks=[
                    # Reconstruct lightweight items
                    type(
                        "Chunk",
                        (),
                        {
                            "chunk_id": uuid.UUID(c["chunk_id"]),
                            "document_id": uuid.UUID(c["document_id"]),
                            "document_name": c["document_name"],
                            "original_filename": c["original_filename"],
                            "source_url": c["source_url"],
                            "content": c["content"],
                            "score": c["score"],
                            "metadata": c["metadata"],
                        },
                    )()
                    for c in ret_item.retrieved_chunks
                ],
                max_chunks=settings.RAG_MAX_CONTEXT_CHUNKS,
                similarity_threshold=settings.RAG_SIMILARITY_THRESHOLD,
            )

            citations_dicts = [c.model_dump(mode="json") for c in citations]
            retrieved_chunk_ids = {str(c["chunk_id"]) for c in ret_item.retrieved_chunks}

            # 2. Check unanswerable / empty context
            t_rag_start = time.perf_counter()
            if not context_str or not case.answerable:
                # LLM should refuse
                if not context_str:
                    generated_answer = "I couldn't find enough information in your uploaded documents to answer that question."
                    ttft_ms = 1.0
                    gen_lat_ms = 1.0
                    tot_lat_ms = (time.perf_counter() - t_rag_start) * 1000
                    prompt_toks = 15
                    comp_toks = 20
                else:
                    # Context exists but information may be absent -> test LLM refusal behavior
                    messages: list[ChatMessage] = [
                        ChatMessage(role="system", content=SYSTEM_RAG_PROMPT),
                        ChatMessage(
                            role="user",
                            content=f"Context from uploaded documents:\n\n{context_str}\n\nUser Question: {case.question}\n\nAnswer using the context above and cite source numbers like [1], [2]:",
                        ),
                    ]
                    ttft_ms = None
                    tokens = []
                    t_llm_start = time.perf_counter()
                    async for tok in self.llm.stream(messages):
                        if ttft_ms is None:
                            ttft_ms = (time.perf_counter() - t_rag_start) * 1000
                        tokens.append(tok)
                    t_llm_end = time.perf_counter()
                    gen_lat_ms = (t_llm_end - t_llm_start) * 1000
                    tot_lat_ms = (t_llm_end - t_rag_start) * 1000
                    generated_answer = "".join(tokens).strip()
                    prompt_toks = len(context_str.split()) + len(case.question.split()) + 50
                    comp_toks = len(generated_answer.split())
            else:
                # Normal answerable turn
                messages = [ChatMessage(role="system", content=SYSTEM_RAG_PROMPT)]
                if case.history:
                    for h in case.history:
                        messages.append(ChatMessage(role=h["role"], content=h["content"]))

                user_prompt = (
                    f"Context from uploaded documents:\n\n{context_str}\n\n"
                    f"User Question: {case.question}\n\n"
                    f"Answer using the context above and cite source numbers like [1], [2]:"
                )
                messages.append(ChatMessage(role="user", content=user_prompt))

                ttft_ms = None
                tokens = []
                t_llm_start = time.perf_counter()
                async for tok in self.llm.stream(messages):
                    if ttft_ms is None:
                        ttft_ms = (time.perf_counter() - t_rag_start) * 1000
                    tokens.append(tok)
                t_llm_end = time.perf_counter()
                gen_lat_ms = (t_llm_end - t_llm_start) * 1000
                tot_lat_ms = (t_llm_end - t_rag_start) * 1000
                generated_answer = "".join(tokens).strip()
                prompt_toks = len(context_str.split()) + len(case.question.split()) + 100
                comp_toks = len(generated_answer.split())

            # 3. Evaluate Metrics
            is_correct, is_refusal, correct_refusal = evaluate_answer_correctness(
                generated_text=generated_answer,
                expected_answer=case.expected_answer,
                expected_keywords=case.expected_keywords,
                answerable=case.answerable,
            )

            groundedness_score, groundedness_reason = evaluate_groundedness(
                generated_text=generated_answer,
                context_text=context_str,
            )

            valid_cits, halluc_cits = validate_citations(
                citations=citations_dicts,
                retrieved_chunk_ids=retrieved_chunk_ids,
                expected_doc=case.expected_document,
                expected_url=case.expected_url,
            )

            cost = estimate_cost(prompt_tokens=prompt_toks, completion_tokens=comp_toks)

            generation_items.append(
                GenerationResultItem(
                    case_id=case.id,
                    category=case.category,
                    question=case.question,
                    answerable=case.answerable,
                    generated_answer=generated_answer,
                    is_correct=is_correct,
                    is_refusal=is_refusal,
                    correct_refusal=correct_refusal,
                    groundedness_score=groundedness_score,
                    groundedness_reason=groundedness_reason,
                    total_citations=len(citations_dicts),
                    valid_citations_count=valid_cits,
                    hallucinated_citations_count=halluc_cits,
                    citations=citations_dicts,
                    ttft_ms=round(ttft_ms or 0.0, 2),
                    generation_latency_ms=round(gen_lat_ms, 2),
                    total_latency_ms=round(tot_lat_ms, 2),
                    prompt_tokens=prompt_toks,
                    completion_tokens=comp_toks,
                    total_tokens=prompt_toks + comp_toks,
                    estimated_cost_usd=cost,
                )
            )

        gen_summary = calculate_generation_metrics(generation_items)

        config_meta = {
            "embedding_model": settings.EMBEDDING_MODEL,
            "embedding_dimensions": settings.EMBEDDING_DIMENSIONS,
            "chunk_size": settings.CHUNK_SIZE,
            "chunk_overlap": settings.CHUNK_OVERLAP,
            "top_k": top_k,
            "rag_max_context_chunks": settings.RAG_MAX_CONTEXT_CHUNKS,
            "rag_similarity_threshold": settings.RAG_SIMILARITY_THRESHOLD,
            "llm_model": settings.LLM_MODEL,
        }

        report = BenchmarkReport(
            timestamp=datetime.datetime.now(datetime.UTC).isoformat(),
            mode="full",
            config=config_meta,
            retrieval_metrics=retrieval_summary,
            generation_metrics=gen_summary,
            detailed_retrieval_results=retrieval_items,
            detailed_generation_results=generation_items,
        )

        return report

    def save_report(self, report: BenchmarkReport) -> Path:
        """Persist benchmark report to JSON artifact."""
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        ts_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"eval_{report.mode}_{ts_str}.json"
        out_path = RESULTS_DIR / filename
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=2))
        logger.info(f"Saved evaluation benchmark report to: {out_path}")
        return out_path
