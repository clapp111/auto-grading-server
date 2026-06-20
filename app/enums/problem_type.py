from enum import Enum


class ProblemType(str, Enum):
    MULTIPLE_CHOICE = "MULTIPLE_CHOICE"
    SHORT_ANSWER = "SHORT_ANSWER"
    DESCRIPTIVE = "DESCRIPTIVE"
    CODING = "CODING"
