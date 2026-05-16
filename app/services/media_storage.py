import logging
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Union

from app.core.config import settings

logger = logging.getLogger(__name__)


class MediaStorageService:
    """Store user media under ``UPLOAD_DIR``; URLs are served from ``/media`` (see ``app.main``)."""

    def __init__(self) -> None:
        self._upload_root = Path(settings.upload_dir).resolve()
        self._upload_root.mkdir(parents=True, exist_ok=True)
        logger.info("Media storage root: %s", self._upload_root)

    def _base_url(self) -> str:
        return settings.public_media_base_url.rstrip("/")

    def _safe_path(self, storage_key: str) -> Path:
        if ".." in Path(storage_key).parts:
            raise ValueError("Invalid storage key")
        path = (self._upload_root / storage_key).resolve()
        if not str(path).startswith(str(self._upload_root)):
            raise ValueError("Invalid storage key path")
        return path

    def _public_url(self, storage_key: str) -> str:
        return f"{self._base_url()}/media/{storage_key}"

    def upload_file(
        self, file_obj, user_id: Union[int, str], original_filename: str
    ) -> Dict[str, Any]:
        try:
            parts = original_filename.rsplit(".", 1)
            file_extension = parts[-1].lower() if len(parts) > 1 else ""
            unique_filename = f"{user_id}/{uuid.uuid4().hex}"
            if file_extension:
                unique_filename += f".{file_extension}"
            dest = self._safe_path(unique_filename)
            dest.parent.mkdir(parents=True, exist_ok=True)
            file_obj.seek(0)
            dest.write_bytes(file_obj.read())
            url = self._public_url(unique_filename)
            return {
                "success": True,
                "filename": unique_filename,
                "original_filename": original_filename,
                "file_url": url,
                "s3_key": unique_filename,
                "bucket": "local",
            }
        except Exception as e:
            logger.error("Local upload error: %s", e)
            return {"success": False, "error": f"Upload failed: {e}"}

    def upload_file_with_public_access(
        self, file_obj, user_id: Union[int, str], original_filename: str
    ) -> Dict[str, Any]:
        return self.upload_file(file_obj, user_id, original_filename)

    def delete_file(self, storage_key: str) -> bool:
        try:
            path = self._safe_path(storage_key)
            if path.is_file():
                path.unlink()
            return True
        except OSError as e:
            logger.error("Local delete error: %s", e)
            return False

    def generate_presigned_url(self, storage_key: str, expiration: int = 3600) -> Optional[str]:
        _ = expiration
        return self._public_url(storage_key)

    def get_file_content(self, storage_key: str) -> Optional[bytes]:
        try:
            path = self._safe_path(storage_key)
            if not path.is_file():
                return None
            return path.read_bytes()
        except OSError as e:
            logger.error("Error reading local file: %s", e)
            return None
