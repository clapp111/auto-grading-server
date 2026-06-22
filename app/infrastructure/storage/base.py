from abc import ABC, abstractmethod


class StorageClient(ABC):
    @abstractmethod
    def generate_key(self, prefix: str, file_name: str) -> str: ...

    @abstractmethod
    def generate_presigned_url(self, file_key: str, content_type: str) -> str: ...

    @abstractmethod
    def download(self, file_key: str) -> bytes: ...
