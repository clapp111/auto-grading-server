from enum import IntEnum


class ExamStep(IntEnum):
    DRAFT = 0
    PROBLEM_SETUP = 1
    RUBRIC = 2
    ANSWER_UPLOAD = 3
    REGION_SETUP = 4
    OCR = 5
    GRADING = 6
    DONE = 7
