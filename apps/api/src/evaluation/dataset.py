import json
import logging
import uuid
from pathlib import Path
from unittest.mock import patch

from apps.api.src.evaluation.schema import EvalCase
from apps.api.src.models.document import Document
from apps.api.src.services.document_service import DocumentService
from apps.api.src.services.ssrf_service import SSRFService
from apps.api.src.services.web_fetcher import FetchedWebPage
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("ai_knowledge_assistant.evaluation.dataset")

FIXTURES_DIR = Path(__file__).parent / "fixtures"
DOCUMENTS_DIR = FIXTURES_DIR / "documents"
DATASET_PATH = FIXTURES_DIR / "eval_dataset.json"


def load_evaluation_dataset() -> list[EvalCase]:
    """Load and parse the evaluation dataset JSON file."""
    if not DATASET_PATH.exists():
        raise FileNotFoundError(f"Evaluation dataset file not found at: {DATASET_PATH}")

    with open(DATASET_PATH, encoding="utf-8") as f:
        raw_cases = json.load(f)

    return [EvalCase.model_validate(item) for item in raw_cases]


async def setup_eval_knowledge_base(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> dict[str, Document]:
    """
    Ingest the 3 synthetic knowledge documents into PostgreSQL + pgvector for the evaluation user:
    1. employee_handbook.md
    2. security_guide.md
    3. api_architecture.html (website source: https://architecture.acmecorp.example/spec)
    """
    logger.info(f"Setting up evaluation knowledge base for user_id={user_id}...")
    documents_map: dict[str, Document] = {}

    # 1. Ingest employee_handbook.md
    handbook_path = DOCUMENTS_DIR / "employee_handbook.md"
    with open(handbook_path, "rb") as f:
        handbook_bytes = f.read()
    handbook_doc = await DocumentService.create_document(
        db=db,
        user_id=user_id,
        content=handbook_bytes,
        original_filename="employee_handbook.md",
        sync_process=True,
    )
    documents_map["employee_handbook.md"] = handbook_doc

    # 2. Ingest security_guide.md
    security_path = DOCUMENTS_DIR / "security_guide.md"
    with open(security_path, "rb") as f:
        security_bytes = f.read()
    security_doc = await DocumentService.create_document(
        db=db,
        user_id=user_id,
        content=security_bytes,
        original_filename="security_guide.md",
        sync_process=True,
    )
    documents_map["security_guide.md"] = security_doc

    # 3. Ingest api_architecture.html (as website source)
    arch_path = DOCUMENTS_DIR / "api_architecture.html"
    with open(arch_path, "rb") as f:
        arch_html_bytes = f.read()

    target_web_url = "https://architecture.acmecorp.example/spec"
    with patch.object(SSRFService, "validate_url", return_value=target_web_url):
        with patch("apps.api.src.services.web_fetcher.WebFetcher.fetch") as mock_fetch:
            mock_fetch.return_value = FetchedWebPage(
                url=target_web_url,
                content=arch_html_bytes,
                content_type="text/html",
                status_code=200,
            )
            arch_doc = await DocumentService.create_website_document(
                db=db,
                user_id=user_id,
                url=target_web_url,
                sync_process=True,
            )
            documents_map["api_architecture.html"] = arch_doc

    logger.info(f"Successfully ingested 3 evaluation documents: {list(documents_map.keys())}")
    return documents_map
