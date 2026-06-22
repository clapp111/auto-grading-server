from sqlalchemy.orm import Session

from app.models.model_answer import ModelAnswer


class ModelAnswerRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_problem_id(self, problem_id: int) -> ModelAnswer | None:
        return self.db.query(ModelAnswer).filter(ModelAnswer.problem_id == problem_id).first()

    def map_by_problem_ids(self, problem_ids: list[int]) -> dict[int, ModelAnswer]:
        rows = self.db.query(ModelAnswer).filter(ModelAnswer.problem_id.in_(problem_ids)).all()
        return {row.problem_id: row for row in rows}

    def get_or_create(self, problem_id: int) -> ModelAnswer:
        existing = self.get_by_problem_id(problem_id)
        if existing:
            return existing
        model_answer = ModelAnswer(problem_id=problem_id)
        self.db.add(model_answer)
        self.db.commit()
        self.db.refresh(model_answer)
        return model_answer

    def update(self, model_answer: ModelAnswer, **kwargs) -> ModelAnswer:
        for key, value in kwargs.items():
            setattr(model_answer, key, value)
        self.db.commit()
        self.db.refresh(model_answer)
        return model_answer
