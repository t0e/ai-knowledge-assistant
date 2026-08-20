import logging
import shutil
from abc import ABC, abstractmethod
from pathlib import Path

from apps.api.src.core.config import settings

logger = logging.getLogger("ai_knowledge_assistant.storage")


class BaseStorageService(ABC):
    """Abstract interface for file storage operations."""

    @abstractmethod
    async def save_file(self, content: bytes, relative_path: str) -> str:
        """Save file bytes to storage and return the stored relative path."""
        pass

    @abstractmethod
    async def read_file(self, relative_path: str) -> bytes:
        """Read file bytes from storage."""
        pass

    @abstractmethod
    async def delete_file(self, relative_path: str) -> bool:
        """Delete file from storage. Returns True if deleted, False if did not exist."""
        pass

    @abstractmethod
    async def file_exists(self, relative_path: str) -> bool:
        """Check if file exists in storage."""
        pass


class LocalStorageService(BaseStorageService):
    """Local filesystem storage implementation with path traversal defense."""

    def __init__(self, base_dir: str | None = None):
        self.base_dir = Path(base_dir or settings.STORAGE_LOCAL_DIR).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized LocalStorageService at {self.base_dir}")

    def _resolve_safe_path(self, relative_path: str) -> Path:
        """Sanitize and resolve path ensuring no escape outside base_dir."""
        # Strip any leading slashes or Windows drive letters
        clean_rel = relative_path.lstrip("/\\")
        target_path = (self.base_dir / clean_rel).resolve()

        if not str(target_path).startswith(str(self.base_dir)):
            logger.error(f"Path traversal attempt detected: {relative_path}")
            raise ValueError("Invalid storage path: directory traversal attempt detected.")

        return target_path

    async def save_file(self, content: bytes, relative_path: str) -> str:
        target_path = self._resolve_safe_path(relative_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)

        temp_path = target_path.with_suffix(target_path.suffix + ".tmp")
        try:
            with open(temp_path, "wb") as f:
                f.write(content)
            temp_path.replace(target_path)
            logger.debug(f"Saved file to {target_path}")
            return relative_path
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            logger.error(f"Failed to save file to {target_path}: {e}")
            raise

    async def read_file(self, relative_path: str) -> bytes:
        target_path = self._resolve_safe_path(relative_path)
        if not target_path.is_file():
            raise FileNotFoundError(f"File not found at {relative_path}")

        with open(target_path, "rb") as f:
            return f.read()

    async def delete_file(self, relative_path: str) -> bool:
        try:
            target_path = self._resolve_safe_path(relative_path)
            if target_path.is_file():
                target_path.unlink()
                # Clean up parent directory if empty
                parent = target_path.parent
                if parent != self.base_dir and not any(parent.iterdir()):
                    shutil.rmtree(parent, ignore_errors=True)
                logger.debug(f"Deleted file {target_path}")
                return True
            return False
        except Exception as e:
            logger.warning(f"Error during file deletion for {relative_path}: {e}")
            return False

    async def file_exists(self, relative_path: str) -> bool:
        try:
            target_path = self._resolve_safe_path(relative_path)
            return target_path.is_file()
        except ValueError:
            return False


_storage_service_instance: BaseStorageService | None = None


def get_storage_service() -> BaseStorageService:
    """Dependency / factory returning singleton storage service."""
    global _storage_service_instance
    if _storage_service_instance is None:
        _storage_service_instance = LocalStorageService()
    return _storage_service_instance
