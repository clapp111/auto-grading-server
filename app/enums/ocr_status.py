from enum import Enum


class OCRStatus(str, Enum):
    RAW = "RAW"
    REVIEWED = "REVIEWED"
