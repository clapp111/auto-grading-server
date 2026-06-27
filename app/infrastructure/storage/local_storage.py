import uuid
from pathlib import Path

from app.core.config import settings
from app.infrastructure.storage.base import StorageClient


class LocalStorageClient(StorageClient):
    """로컬 개발용 스텁. Presigned URL은 S3/LocalStack 없이 동작하지 않으므로
    실제 업로드 없이 file_key만 생성한다."""

    def generate_key(self, prefix: str, file_name: str) -> str:
        ext = Path(file_name).suffix
        return f"{prefix}/{uuid.uuid4().hex}{ext}"

    def generate_presigned_url(self, file_key: str, content_type: str) -> str:
        return f"http://localhost:LOCAL_STUB/{file_key}"

    def download(self, file_key: str) -> bytes:
        path = Path(settings.LOCAL_STORAGE_PATH) / file_key
        return path.read_bytes()

    def delete(self, file_key: str) -> None:
        path = Path(settings.LOCAL_STORAGE_PATH) / file_key
        path.unlink(missing_ok=True)
