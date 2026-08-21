import asyncio
import re
from collections.abc import AsyncGenerator

from apps.api.src.llm.base import BaseLLMProvider, ChatMessage


class MockLLMProvider(BaseLLMProvider):
    """
    Deterministic mock LLM provider for unit and integration testing.
    Generates grounded answers based on supplied [SOURCE_x] context tags.
    """

    def __init__(self, model_name: str = "mock-gpt-v1", token_delay_s: float = 0.005):
        self._model_name = model_name
        self._token_delay = token_delay_s

    @property
    def model_name(self) -> str:
        return self._model_name

    def _synthesize_answer(self, messages: list[ChatMessage]) -> str:
        # Extract user query and any context blocks
        user_message = ""
        for m in reversed(messages):
            if m.role == "user":
                user_message = m.content
                break

        # Look for [SOURCE_x] blocks in system or user messages
        all_text = " ".join([m.content for m in messages])
        source_matches = re.findall(
            r"\[SOURCE_(\d+)\]\s*Document:\s*([^\n]+)(.*?)(?=\[SOURCE_|\n\nUser Question:|\n\nAnswer using|\Z)",
            all_text,
            re.DOTALL,
        )

        # Check for insufficient context or unanswerable queries
        if not source_matches or "insufficient" in user_message.lower():
            return "I couldn't find enough information in your uploaded documents to answer that question."

        # Check for prompt injection attempt inside context or query
        if (
            "ignore all previous instructions" in user_message.lower()
            or "reveal the system prompt" in user_message.lower()
        ):
            return "I am an AI assistant strictly answering questions grounded in your uploaded documents. [1]"

        # Extract question part from user prompt
        if "User Question:" in user_message:
            actual_question = (
                user_message.split("User Question:", 1)[-1].split("Answer using", 1)[0].strip()
            )
        else:
            actual_question = user_message.strip()

        stop_words = {
            "what",
            "when",
            "where",
            "which",
            "how",
            "many",
            "does",
            "from",
            "with",
            "that",
            "this",
            "user",
            "question",
            "context",
            "uploaded",
            "documents",
            "answer",
            "about",
            "using",
            "above",
            "cite",
            "source",
            "numbers",
            "like",
            "who",
            "whom",
            "whose",
            "the",
            "and",
            "are",
            "for",
            "was",
            "were",
            "been",
            "can",
            "could",
            "would",
            "should",
            "will",
            "shall",
            "give",
            "tell",
            "version",
            "guidelines",
            "policy",
            "status",
            "methods",
            "process",
            "system",
            "access",
        }
        q_words = [
            w
            for w in re.findall(r"\b[A-Za-z0-9_]{3,}\b", actual_question.lower())
            if w not in stop_words
        ]

        # Extract only actual content from retrieved sources
        retrieved_content = " ".join(body for _, _, body in source_matches).lower()
        matching_content_words = sum(1 for w in q_words if w in retrieved_content)

        # If question has key subject terms and none appear in retrieved chunk content, refuse properly!
        if q_words and matching_content_words == 0:
            return "I couldn't find enough information in your uploaded documents to answer that question."

        # Grounded response synthesis: only synthesize sources containing query terms
        summary_sentences = []

        for src_id, doc_name, body in source_matches:
            # Extract content from body
            if "Content:" in body:
                content_part = body.split("Content:", 1)[-1].strip()
            else:
                content_part = body.strip()

            # Verify chunk actually contains relevant query terms
            chunk_lower = content_part.lower()
            if q_words and not any(w in chunk_lower for w in q_words):
                continue

            cleaned_content = re.sub(r"[\n\r\t]+", " ", content_part).strip()
            # Strip markdown hashes
            cleaned_content = re.sub(r"^#+\s*", "", cleaned_content)
            snippet = cleaned_content[:250] if len(cleaned_content) > 250 else cleaned_content
            if snippet:
                summary_sentences.append(
                    f"According to {doc_name.strip()}, {snippet.rstrip('.')} [{src_id}]."
                )

        if not summary_sentences:
            return "I couldn't find enough information in your uploaded documents to answer that question."

        return " ".join(summary_sentences[:3])

    async def generate(
        self,
        messages: list[ChatMessage],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        return self._synthesize_answer(messages)

    async def stream(
        self,
        messages: list[ChatMessage],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[str, None]:
        full_text = self._synthesize_answer(messages)
        # Split into word/punctuation tokens for realistic streaming
        tokens = re.findall(r"\S+|\s+", full_text)
        for token in tokens:
            if self._token_delay > 0:
                await asyncio.sleep(self._token_delay)
            yield token
