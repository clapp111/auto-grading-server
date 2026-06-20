from enum import Enum


class GradeMethod(str, Enum):
    AUTO = "AUTO"
    LLM = "LLM"
    HUMAN = "HUMAN"
