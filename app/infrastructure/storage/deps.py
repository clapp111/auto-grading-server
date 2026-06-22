from app.core.config import settings
from app.infrastructure.storage.base import StorageClient
from app.infrastructure.storage.local_storage import LocalStorageClient
from app.infrastructure.storage.s3_storage import S3StorageClient


def get_storage() -> StorageClient:
    if settings.STORAGE_BACKEND == "s3":
        return S3StorageClient()
    return LocalStorageClient()
