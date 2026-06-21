from app.core.config import settings


def get_file_url(file_key: str | None) -> str | None:
    if not file_key:
        return None

    if settings.STORAGE_BACKEND == "s3":
        if settings.CDN_BASE_URL:
            return f"{settings.CDN_BASE_URL.rstrip('/')}/{file_key}"
        return f"https://{settings.S3_BUCKET}.s3.{settings.S3_REGION}.amazonaws.com/{file_key}"

    base = settings.APP_BASE_URL.rstrip("/")
    return f"{base}/uploads/{file_key}"
