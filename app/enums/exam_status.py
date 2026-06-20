from enum import Enum


class ExamStatus(str, Enum):
    DRAFT = "DRAFT"
    SETUP = "SETUP"
    OCR = "OCR"
    GRADING = "GRADING"
    DONE = "DONE"
