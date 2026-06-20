from enum import Enum


class Position(str, Enum):
    PROFESSOR = "PROFESSOR"
    TEACHER = "TEACHER"
    TUTOR = "TUTOR"
    TA = "TA"
