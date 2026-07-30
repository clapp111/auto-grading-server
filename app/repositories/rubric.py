from sqlalchemy.orm import Session

from app.enums.rubric_source import RubricSource
from app.models.rubric import Rubric


class RubricRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, rubric_id: int) -> Rubric | None:
        return self.db.get(Rubric, rubric_id)

    def list_by_problem(self, problem_id: int) -> list[Rubric]:
        return (
            self.db.query(Rubric)
            .filter(Rubric.problem_id == problem_id)
            .order_by(Rubric.order_index)
            .all()
        )

    def map_by_problem_ids(self, problem_ids: list[int]) -> dict[int, list[Rubric]]:
        if not problem_ids:
            return {}
        rubrics = (
            self.db.query(Rubric)
            .filter(Rubric.problem_id.in_(problem_ids))
            .order_by(Rubric.problem_id, Rubric.order_index)
            .all()
        )
        result: dict[int, list[Rubric]] = {}
        for r in rubrics:
            result.setdefault(r.problem_id, []).append(r)
        return result

    def max_order_index(self, problem_id: int) -> int:
        from sqlalchemy import func

        result = (
            self.db.query(func.max(Rubric.order_index))
            .filter(Rubric.problem_id == problem_id)
            .scalar()
        )
        return result if result is not None else -1

    def create(
        self,
        problem_id: int,
        text: str,
        allocated_score: int,
        source: RubricSource,
        order_index: int,
    ) -> Rubric:
        rubric = Rubric(
            problem_id=problem_id,
            text=text,
            allocated_score=allocated_score,
            source=source,
            order_index=order_index,
        )
        self.db.add(rubric)
        self.db.commit()
        self.db.refresh(rubric)
        return rubric

    def bulk_create(
        self, problem_id: int, criteria: list[dict], source: RubricSource
    ) -> list[Rubric]:
        rubrics = [
            Rubric(
                problem_id=problem_id,
                text=c["text"],
                allocated_score=c["allocated_score"],
                source=source,
                order_index=i,
            )
            for i, c in enumerate(criteria)
        ]
        self.db.add_all(rubrics)
        self.db.commit()
        for r in rubrics:
            self.db.refresh(r)
        return rubrics

    def delete_by_problem(self, problem_id: int) -> None:
        self.db.query(Rubric).filter(Rubric.problem_id == problem_id).delete()
        self.db.commit()

    def update(self, rubric: Rubric, **kwargs) -> Rubric:
        for key, value in kwargs.items():
            setattr(rubric, key, value)
        self.db.commit()
        self.db.refresh(rubric)
        return rubric

    def delete(self, rubric: Rubric) -> None:
        self.db.delete(rubric)
        self.db.commit()
