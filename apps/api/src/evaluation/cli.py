import argparse
import asyncio
import datetime
import logging
import uuid

from apps.api.src.core.database import AsyncSessionLocal
from apps.api.src.core.security import hash_password
from apps.api.src.evaluation.dataset import load_evaluation_dataset, setup_eval_knowledge_base
from apps.api.src.evaluation.runner import EvaluationRunner
from apps.api.src.evaluation.schema import BenchmarkReport
from apps.api.src.models.user import User

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("ai_knowledge_assistant.evaluation.cli")


def print_human_readable_report(report: BenchmarkReport):
    """Render a clean GitHub/Terminal formatted summary table."""
    rm = report.retrieval_metrics
    gm = report.generation_metrics

    print("\n" + "=" * 70)
    print("                 RAG EVALUATION BENCHMARK REPORT")
    print("=" * 70)
    print(f"Timestamp:   {report.timestamp}")
    print(f"Mode:        {report.mode.upper()}")
    print(f"Questions:   {rm.total_questions} (Answerable: {rm.answerable_questions})")
    print(
        f"Model:       {report.config.get('llm_model')} | Embedding: {report.config.get('embedding_model')}"
    )
    print("-" * 70)

    print("\n[1] RETRIEVAL PERFORMANCE")
    print(f"  • Hit@1:                {rm.hit_at_1_rate:6.2f}%")
    print(f"  • Hit@3:                {rm.hit_at_3_rate:6.2f}%")
    print(f"  • Hit@5:                {rm.hit_at_5_rate:6.2f}%")
    print(f"  • MRR (Mean Recip Rank): {rm.mrr:6.4f}")
    print(f"  • Avg Retrieval Latency: {rm.avg_retrieval_latency_ms:6.2f} ms")

    if gm:
        print("\n[2] GENERATION & GROUNDEDNESS")
        print(f"  • Answer Correctness:   {gm.correctness_rate:6.2f}%")
        print(f"  • Avg Groundedness:     {gm.avg_groundedness:6.2f} / 4.00")
        print(
            f"  • Unanswerable Handled: {gm.unanswerable_correctly_refused}/{gm.unanswerable_total} ({gm.unanswerable_refusal_rate:.1f}% refused)"
        )

        print("\n[3] CITATION ACCURACY")
        print(f"  • Total Citations:      {gm.total_citations}")
        print(f"  • Valid Citations:      {gm.valid_citations_rate:6.2f}%")
        print(f"  • Hallucinated Citations: {gm.hallucinated_citations_count}")

        print("\n[4] OPERATIONAL METRICS & LATENCY")
        print(f"  • Avg Time to 1st Token (TTFT): {gm.avg_ttft_ms:6.2f} ms")
        print(f"  • Avg Generation Latency:       {gm.avg_generation_latency_ms:6.2f} ms")
        print(f"  • Avg Total Request Latency:    {gm.avg_total_latency_ms:6.2f} ms")
        print(
            f"  • Total Tokens:                 {gm.total_tokens} (Prompt: {gm.total_prompt_tokens}, Comp: {gm.total_completion_tokens})"
        )
        print(f"  • Estimated Cost:               ${gm.total_estimated_cost_usd:8.6f} USD")

    print("\n[5] FAILED / WEAK RETRIEVAL CASES")
    failed_cases = [r for r in report.detailed_retrieval_results if r.answerable and not r.hit_at_5]
    if not failed_cases:
        print("  • None! All answerable questions achieved Top-5 retrieval hit.")
    else:
        for fc in failed_cases:
            print(f'  • [{fc.case_id}] "{fc.question}"')
            print(f"    Expected: {fc.expected_doc} -> Heading: {fc.expected_heading}")
            print(f"    Reason:   {fc.failure_reason}")

    print("=" * 70 + "\n")


async def main_async(args):
    dataset = load_evaluation_dataset()
    logger.info(f"Loaded {len(dataset)} evaluation questions from dataset.")

    async with AsyncSessionLocal() as db:
        # Create or fetch evaluation user
        eval_user_email = (
            f"eval_runner_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}@evaluation.local"
        )
        eval_user = User(
            id=uuid.uuid4(),
            email=eval_user_email,
            password_hash=hash_password("EvaluationPassword123!"),
        )
        db.add(eval_user)
        await db.commit()
        logger.info(f"Created dedicated evaluation user: {eval_user.email} (id={eval_user.id})")

        # Setup evaluation documents in pgvector
        await setup_eval_knowledge_base(db, eval_user.id)

        runner = EvaluationRunner()

        if args.mode == "retrieval":
            logger.info("Executing retrieval-only evaluation...")
            items, summary = await runner.evaluate_retrieval_only(
                db=db,
                user_id=eval_user.id,
                cases=dataset,
                top_k=args.top_k,
            )
            report = BenchmarkReport(
                timestamp=datetime.datetime.now(datetime.UTC).isoformat(),
                mode="retrieval",
                config={"top_k": args.top_k},
                retrieval_metrics=summary,
                detailed_retrieval_results=items,
            )
        else:
            logger.info("Executing full end-to-end RAG evaluation...")
            report = await runner.evaluate_full_rag(
                db=db,
                user_id=eval_user.id,
                cases=dataset,
                top_k=args.top_k,
            )

        saved_path = runner.save_report(report)
        print_human_readable_report(report)
        print(f"Artifact written to: {saved_path}")


def main():
    parser = argparse.ArgumentParser(description="AI Knowledge Assistant RAG Evaluation Suite")
    parser.add_argument(
        "--mode",
        choices=["retrieval", "full"],
        default="retrieval",
        help="Evaluation mode: 'retrieval' (fast, no paid LLM calls) or 'full' (end-to-end RAG with generation and citations)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of chunks to retrieve per question (default: 5)",
    )
    args = parser.parse_args()

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
