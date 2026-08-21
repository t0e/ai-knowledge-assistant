from apps.api.src.api.v1.endpoints import auth, chat, conversations, documents, health, search
from fastapi import APIRouter

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(health.router)
api_router.include_router(documents.router)
api_router.include_router(search.router)
api_router.include_router(conversations.router)
api_router.include_router(chat.router)
