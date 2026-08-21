import logging
import uuid

from apps.api.src.core.exceptions import NotFoundException
from apps.api.src.models.conversation import Conversation
from apps.api.src.models.message import Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

logger = logging.getLogger("ai_knowledge_assistant.services.conversation")


class ConversationService:
    """Service managing conversations, messages, and user ownership boundaries."""

    @staticmethod
    async def create_conversation(
        db: AsyncSession,
        user_id: uuid.UUID,
        title: str | None = None,
    ) -> Conversation:
        """Create a new conversation belonging to the user."""
        conversation = Conversation(
            id=uuid.uuid4(),
            user_id=user_id,
            title=(title or "New Conversation").strip()[:255],
        )
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
        logger.info(f"Created conversation id={conversation.id} for user_id={user_id}")
        return conversation

    @staticmethod
    async def list_conversations(
        db: AsyncSession,
        user_id: uuid.UUID,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[tuple[Conversation, int]], int]:
        """List user-scoped conversations with message counts ordered by updated_at descending."""
        offset = (page - 1) * page_size

        # Count total
        count_stmt = select(func.count(Conversation.id)).where(Conversation.user_id == user_id)
        total = (await db.execute(count_stmt)).scalar_one() or 0

        # Query conversations with message count
        stmt = (
            select(
                Conversation,
                func.count(Message.id).label("message_count"),
            )
            .outerjoin(Message, Conversation.id == Message.conversation_id)
            .where(Conversation.user_id == user_id)
            .group_by(Conversation.id)
            .order_by(Conversation.updated_at.desc())
            .offset(offset)
            .limit(page_size)
        )
        result = await db.execute(stmt)
        items = list(result.all())
        return items, total

    @staticmethod
    async def get_conversation(
        db: AsyncSession,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ) -> Conversation:
        """Retrieve conversation and all associated messages with strict user ownership filter."""
        stmt = (
            select(Conversation)
            .options(selectinload(Conversation.messages))
            .where(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
        )
        result = await db.execute(stmt)
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise NotFoundException("Conversation", str(conversation_id))
        return conversation

    @staticmethod
    async def update_conversation_title(
        db: AsyncSession,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
        title: str,
    ) -> Conversation:
        """Update the title of an existing conversation."""
        conversation = await ConversationService.get_conversation(db, user_id, conversation_id)
        conversation.title = title.strip()[:255]
        await db.commit()
        await db.refresh(conversation)
        return conversation

    @staticmethod
    async def delete_conversation(
        db: AsyncSession,
        user_id: uuid.UUID,
        conversation_id: uuid.UUID,
    ) -> bool:
        """Delete conversation and cascade delete all messages."""
        conversation = await ConversationService.get_conversation(db, user_id, conversation_id)
        await db.delete(conversation)
        await db.commit()
        logger.info(f"Deleted conversation id={conversation_id} for user_id={user_id}")
        return True

    @staticmethod
    async def add_message(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        role: str,
        content: str,
        citations: list[dict] | None = None,
    ) -> Message:
        """Add a message to a conversation."""
        message = Message(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            role=role,
            content=content,
            citations=citations or [],
        )
        db.add(message)
        await db.commit()
        await db.refresh(message)
        return message

    @staticmethod
    async def get_recent_messages(
        db: AsyncSession,
        conversation_id: uuid.UUID,
        limit: int = 6,
    ) -> list[Message]:
        """Fetch the most recent N messages in chronological order."""
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        messages = list(result.scalars().all())
        messages.reverse()  # Chronological order
        return messages
