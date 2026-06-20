from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# import all models here so Alembic autogenerate can detect them
from app.models.member import Member  # noqa: F401, E402
from app.models.exam import Exam  # noqa: F401, E402
from app.models.problem import Problem  # noqa: F401, E402
from app.models.model_answer import ModelAnswer  # noqa: F401, E402
from app.models.rubric import Rubric  # noqa: F401, E402
from app.models.student import Student  # noqa: F401, E402
from app.models.answer_sheet import AnswerSheet  # noqa: F401, E402
from app.models.answer_region import AnswerRegion  # noqa: F401, E402
from app.models.ocr_result import OCRResult  # noqa: F401, E402
from app.models.grade import Grade  # noqa: F401, E402
from app.models.job import Job  # noqa: F401, E402
