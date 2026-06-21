from enum import Enum


class AffiliationRole(str, Enum):
    PROFESSOR = "PROFESSOR"
    TEACHER = "TEACHER"
    TUTOR = "TUTOR"
    TA = "TA"
