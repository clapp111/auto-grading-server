import uuid
from pathlib import Path

import boto3

from app.core.config import settings
from app.infrastructure.storage.base import StorageClient


class S3StorageClient(StorageClient):
    def __init__(self):
        self._client = boto3.client(
            "s3",
            region_name=settings.S3_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )

    def generate_key(self, prefix: str, file_name: str) -> str:
        ext = Path(file_name).suffix
        return f"{prefix}/{uuid.uuid4().hex}{ext}"

    def generate_presigned_url(self, file_key: str, content_type: str) -> str:
        return self._client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.S3_BUCKET,
                "Key": file_key,
                "ContentType": content_type,
            },
            ExpiresIn=60,  # 1분
        )

    def download(self, file_key: str) -> bytes:
        response = self._client.get_object(Bucket=settings.S3_BUCKET, Key=file_key)
        return response["Body"].read()
