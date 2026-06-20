from enum import Enum


class RubricSource(str, Enum):
    LLM = "LLM"
    HUMAN = "HUMAN"
