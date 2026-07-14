import mimetypes

from google.api_core.client_options import ClientOptions
from google.cloud import documentai
from google.oauth2 import service_account

from app.core.config import settings
from app.infrastructure.ocr.base import OcrClient


class GoogleDocAiOcrClient(OcrClient):
    def __init__(self):
        credentials = None
        if settings.GOOGLE_APPLICATION_CREDENTIALS:
            credentials = service_account.Credentials.from_service_account_file(
                settings.GOOGLE_APPLICATION_CREDENTIALS
            )

        self._client = documentai.DocumentProcessorServiceClient(
            credentials=credentials,
            client_options=ClientOptions(
                api_endpoint=f"{settings.GOOGLE_DOCAI_LOCATION}-documentai.googleapis.com"
            ),
        )
        self._processor_name = self._client.processor_path(
            settings.GOOGLE_DOCAI_PROJECT_ID,
            settings.GOOGLE_DOCAI_LOCATION,
            settings.GOOGLE_DOCAI_PROCESSOR_ID,
        )

    def recognize(self, image_data: bytes, file_format: str = "jpeg") -> str:
        mime_type = mimetypes.guess_type(f"file.{file_format}")[0] or "image/jpeg"
        request = documentai.ProcessRequest(
            name=self._processor_name,
            raw_document=documentai.RawDocument(content=image_data, mime_type=mime_type),
        )
        result = self._client.process_document(request=request)
        return result.document.text
