from abc import ABC, abstractmethod


class OcrClient(ABC):
    @abstractmethod
    def recognize(self, image_data: bytes, file_format: str = "jpeg") -> str:
        """이미지 바이트를 받아 인식된 텍스트를 반환한다."""
        ...
