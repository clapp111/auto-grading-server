import base64
import time
import uuid

import requests

from app.core.config import settings
from app.infrastructure.ocr.base import OcrClient


class ClovaOcrClient(OcrClient):
    def recognize(self, image_data: bytes, file_format: str = "jpeg") -> str:
        payload = {
            "version": "V2",
            "requestId": str(uuid.uuid4()),
            "timestamp": int(time.time() * 1000),
            "images": [
                {
                    "format": file_format,
                    "name": "ocr_target",
                    "data": base64.b64encode(image_data).decode(),
                }
            ],
        }
        response = requests.post(
            settings.CLOVA_OCR_INVOKE_URL,
            headers={
                "X-OCR-SECRET": settings.CLOVA_OCR_SECRET_KEY,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )
        response.raise_for_status()

        fields = response.json()["images"][0].get("fields", [])
        return " ".join(f["inferText"] for f in fields)
