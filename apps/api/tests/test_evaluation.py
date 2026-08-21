import pytest
from apps.api.src.evaluation.dataset import load_evaluation_dataset
from apps.api.src.evaluation.metrics import (
    calculate_retrieval_metrics,
    compute_retrieval_hit,
    estimate_cost,
    evaluate_answer_correctness,
    evaluate_groundedness,
    validate_citations,
)
from apps.api.src.evaluation.schema import (
    EvalCase,
    RetrievalResultItem,
)


def test_load_evaluation_dataset_structure():
    """Verify evaluation dataset loads and parses correctly with all required categories."""
    dataset = load_evaluation_dataset()
    assert len(dataset) >= 20

    categories = {case.category for case in dataset}
    assert "direct_factual" in categories
    assert "semantic_paraphrased" in categories
    assert "multi_source" in categories
    assert "follow_up" in categories
    assert "unanswerable" in categories
    assert "partially_answerable" in categories
    assert "website" in categories

    for case in dataset:
        assert isinstance(case, EvalCase)
        assert case.id
        assert case.question
        if not case.answerable:
            assert case.category == "unanswerable"


def test_compute_retrieval_hit_rank_1():
    """Verify rank 1 hit yields 100% hits and reciprocal rank 1.0."""
    chunks = [
        {
            "document_name": "employee_handbook.md",
            "content": "Employees receive 25 days of annual leave.",
            "metadata": {"heading": "Annual Leave"},
        }
    ]
    hit_1, hit_3, hit_5, rank, mrr, err = compute_retrieval_hit(
        retrieved_chunks=chunks,
        expected_doc="employee_handbook.md",
        expected_heading="Annual Leave",
        expected_url=None,
        expected_keywords=["25 days"],
        top_k=5,
    )
    assert hit_1 is True
    assert hit_3 is True
    assert hit_5 is True
    assert rank == 1
    assert mrr == 1.0
    assert err is None


def test_compute_retrieval_hit_rank_3():
    """Verify rank 3 hit yields Hit@3 and MRR 0.333."""
    chunks = [
        {"document_name": "other.pdf", "content": "Unrelated", "metadata": {}},
        {"document_name": "other2.pdf", "content": "Unrelated", "metadata": {}},
        {
            "document_name": "security_guide.md",
            "content": "JWT expires in 15 minutes.",
            "metadata": {"heading": "Auth"},
        },
    ]
    hit_1, hit_3, hit_5, rank, mrr, err = compute_retrieval_hit(
        retrieved_chunks=chunks,
        expected_doc="security_guide.md",
        expected_heading="Auth",
        expected_url=None,
        expected_keywords=["15 minutes"],
        top_k=5,
    )
    assert hit_1 is False
    assert hit_3 is True
    assert hit_5 is True
    assert rank == 3
    assert mrr == pytest.approx(1.0 / 3, 0.001)


def test_compute_retrieval_hit_not_in_top_5():
    """Verify missed chunk yields Hit=False and MRR 0.0."""
    chunks = [{"document_name": "other.pdf", "content": "Unrelated", "metadata": {}}]
    hit_1, hit_3, hit_5, rank, mrr, err = compute_retrieval_hit(
        retrieved_chunks=chunks,
        expected_doc="security_guide.md",
        expected_heading="Auth",
        expected_url=None,
        expected_keywords=["15 minutes"],
        top_k=5,
    )
    assert hit_1 is False
    assert hit_3 is False
    assert hit_5 is False
    assert rank is None
    assert mrr == 0.0
    assert "not found in Top 5" in err


def test_calculate_retrieval_metrics_aggregation():
    """Verify retrieval metric aggregation calculations."""
    results = [
        RetrievalResultItem(
            case_id="1",
            category="direct",
            question="q1",
            answerable=True,
            hit_at_1=True,
            hit_at_3=True,
            hit_at_5=True,
            rank=1,
            reciprocal_rank=1.0,
        ),
        RetrievalResultItem(
            case_id="2",
            category="direct",
            question="q2",
            answerable=True,
            hit_at_1=False,
            hit_at_3=True,
            hit_at_5=True,
            rank=2,
            reciprocal_rank=0.5,
        ),
        RetrievalResultItem(
            case_id="3",
            category="unans",
            question="q3",
            answerable=False,
            hit_at_1=False,
            hit_at_3=False,
            hit_at_5=False,
            rank=None,
            reciprocal_rank=0.0,
        ),
    ]
    summary = calculate_retrieval_metrics(results)
    assert summary.total_questions == 3
    assert summary.answerable_questions == 2
    assert summary.hit_at_1_rate == 50.0
    assert summary.hit_at_3_rate == 100.0
    assert summary.hit_at_5_rate == 100.0
    assert summary.mrr == 0.75


def test_evaluate_answer_correctness_and_refusals():
    """Verify answer correctness deterministic evaluation."""
    # Correct answer
    correct, refusal, correct_refusal = evaluate_answer_correctness(
        generated_text="Full-time employees receive 25 days of annual leave.",
        expected_answer="25 days",
        expected_keywords=["25 days", "annual leave"],
        answerable=True,
    )
    assert correct is True
    assert refusal is False

    # Unanswerable question correctly refused
    correct, refusal, correct_refusal = evaluate_answer_correctness(
        generated_text="I couldn't find enough information in your uploaded documents to answer that question.",
        expected_answer=None,
        expected_keywords=[],
        answerable=False,
    )
    assert correct is True
    assert refusal is True
    assert correct_refusal is True

    # Unanswerable question hallucinated
    correct, refusal, correct_refusal = evaluate_answer_correctness(
        generated_text="The winner of the 2018 World Cup was France.",
        expected_answer=None,
        expected_keywords=[],
        answerable=False,
    )
    assert correct is False
    assert refusal is False
    assert correct_refusal is False


def test_evaluate_groundedness_rubric():
    """Verify groundedness scoring rubric."""
    context = "Acme Corp operates a remote-first workplace model with a $1,000 allowance."

    # High overlap (score 4)
    score_high, _ = evaluate_groundedness(
        generated_text="Acme Corp operates a remote-first model with $1,000 allowance.",
        context_text=context,
    )
    assert score_high == 4

    # Low overlap / hallucination (score 0-1)
    score_low, _ = evaluate_groundedness(
        generated_text="Employees receive unlimited cryptocurrency grants and luxury sports cars.",
        context_text=context,
    )
    assert score_low in (0, 1)


def test_validate_citations_and_cost_estimation():
    """Verify citation validity checks and pricing calculations."""
    citations = [
        {"chunk_id": "c1", "source_id": 1, "document_name": "doc.md"},
        {"chunk_id": "c2", "source_id": 2, "document_name": "doc.md"},
    ]
    retrieved_ids = {"c1", "c2"}
    valid, halluc = validate_citations(citations, retrieved_ids, "doc.md", None)
    assert valid == 2
    assert halluc == 0

    # Cost calculation: 1000 prompt tokens + 200 completion tokens
    cost = estimate_cost(prompt_tokens=1000, completion_tokens=200)
    assert cost > 0.0
