from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.exceptions import ExamNotFoundError, GradeNotFoundError, ProblemNotFoundError
from app.db.session import get_db
from app.enums.grade_method import GradeMethod
from app.enums.grade_status import GradeStatus
from app.enums.job_type import JobType
from app.enums.problem_type import ProblemType
from app.models.grade import Grade
from app.models.rubric import Rubric
from app.models.ocr_result import OCRResult
from app.repositories.exam import ExamRepository
from app.repositories.grade import GradeRepository
from app.repositories.job import JobRepository
from app.repositories.model_answer import ModelAnswerRepository
from app.repositories.ocr_result import OcrResultRepository
from app.repositories.problem import ProblemRepository
from app.repositories.rubric import RubricRepository
from app.repositories.student import StudentRepository
from app.schemas.grade import (
    GradeBulkConfirmResponse,
    GradingProgressResponse,
    GradeResponse,
    GradeUpdateRequest,
    ProblemGradingItem,
    RubricResultItem,
)
from app.schemas.job import JobStartedResponse

_LLM_TYPES = {ProblemType.DESCRIPTIVE, ProblemType.CODING}


class GradeService:
    def __init__(
        self,
        grade_repo: GradeRepository,
        problem_repo: ProblemRepository,
        exam_repo: ExamRepository,
        rubric_repo: RubricRepository,
        ocr_result_repo: OcrResultRepository,
        model_answer_repo: ModelAnswerRepository,
        student_repo: StudentRepository,
        job_repo: JobRepository,
    ):
        self.grade_repo = grade_repo
        self.problem_repo = problem_repo
        self.exam_repo = exam_repo
        self.rubric_repo = rubric_repo
        self.ocr_result_repo = ocr_result_repo
        self.model_answer_repo = model_answer_repo
        self.student_repo = student_repo
        self.job_repo = job_repo

    def _get_exam_or_raise(self, exam_id: int, member_id: int):
        exam = self.exam_repo.get_by_id(exam_id)
        if not exam or exam.member_id != member_id:
            raise ExamNotFoundError()
        return exam

    def _get_problem_or_raise(self, problem_id: int, member_id: int):
        problem = self.problem_repo.get_by_id(problem_id)
        if not problem:
            raise ProblemNotFoundError()
        exam = self.exam_repo.get_by_id(problem.exam_id)
        if not exam or exam.member_id != member_id:
            raise ProblemNotFoundError()
        return problem

    def _get_grade_or_raise(self, grade_id: int, member_id: int) -> Grade:
        grade = self.grade_repo.get_by_id(grade_id)
        if not grade:
            raise GradeNotFoundError()
        problem = self.problem_repo.get_by_id(grade.problem_id)
        if not problem:
            raise GradeNotFoundError()
        exam = self.exam_repo.get_by_id(problem.exam_id)
        if not exam or exam.member_id != member_id:
            raise GradeNotFoundError()
        return grade

    def get_grading_progress(self, exam_id: int, member_id: int) -> GradingProgressResponse:
        self._get_exam_or_raise(exam_id, member_id)
        problems = self.problem_repo.list_by_exam(exam_id)
        student_count = self.student_repo.count_by_exam(exam_id)

        total_confirmed = 0
        total_possible = student_count * len(problems)
        items: list[ProblemGradingItem] = []

        count_map = self.grade_repo.count_by_problems([p.problem_id for p in problems])
        for problem in problems:
            _, confirmed = count_map.get(problem.problem_id, (0, 0))
            total_confirmed += confirmed
            percent = (confirmed * 100 // student_count) if student_count > 0 else 0
            items.append(ProblemGradingItem(
                problem_id=problem.problem_id,
                label=problem.label,
                type=problem.type,
                max_score=problem.max_score,
                confirmed_count=confirmed,
                total_count=student_count,
                percent=percent,
            ))

        return GradingProgressResponse(
            confirmed_count=total_confirmed,
            total_count=total_possible,
            problems=items,
        )

    def run_grade(self, exam_id: int, problem_id: int, member_id: int) -> JobStartedResponse:
        from app.workers.grade_tasks import run_auto_grade, run_llm_grade

        self._get_exam_or_raise(exam_id, member_id)
        problem = self._get_problem_or_raise(problem_id, member_id)

        is_llm = problem.type in _LLM_TYPES
        job_type = JobType.LLM_GRADE if is_llm else JobType.AUTO_GRADE
        job = self.job_repo.create(
            exam_id=exam_id,
            problem_id=problem_id,
            type=job_type,
            requested_by_member_id=member_id,
            input_json={
                "scope": {"examId": exam_id, "problemId": problem_id},
                "source": {
                    "trigger": "api",
                    "endpoint": f"/api/v1/exams/{exam_id}/problems/{problem_id}/grade/run",
                },
            },
        )

        if is_llm:
            run_llm_grade.delay(job.job_id)
        else:
            run_auto_grade.delay(job.job_id)

        self.exam_repo.touch(exam_id)
        return JobStartedResponse(job_id=job.job_id, status=job.status)

    def list_grades(self, problem_id: int, member_id: int) -> list[GradeResponse]:
        problem = self._get_problem_or_raise(problem_id, member_id)
        grades = self.grade_repo.list_by_problem(problem_id)
        rubrics = self.rubric_repo.list_by_problem(problem_id)
        ocr_map = self.ocr_result_repo.map_by_problem(problem_id)
        model_answer = self.model_answer_repo.get_by_problem_id(problem_id)
        model_answer_text = model_answer.model_answer_text if model_answer else None

        student_map = self.student_repo.map_by_ids([g.student_id for g in grades])

        return [
            _to_response(
                grade,
                student_map[grade.student_id].name,
                student_map[grade.student_id].student_no,
                problem.max_score,
                rubrics,
                ocr_map.get(grade.student_id),
                model_answer_text,
            )
            for grade in grades
        ]

    def _build_grade_response(self, grade: Grade, problem, exam_id: int) -> GradeResponse:
        student = self.student_repo.get_by_id(grade.student_id)
        rubrics = self.rubric_repo.list_by_problem(grade.problem_id)
        ocr_map = self.ocr_result_repo.map_by_problem(grade.problem_id)
        model_answer = self.model_answer_repo.get_by_problem_id(grade.problem_id)
        model_answer_text = model_answer.model_answer_text if model_answer else None
        self.exam_repo.touch(exam_id)
        return _to_response(grade, student.name, student.student_no, problem.max_score, rubrics, ocr_map.get(grade.student_id), model_answer_text)

    def update_grade(self, grade_id: int, member_id: int, request: GradeUpdateRequest) -> GradeResponse:
        grade = self._get_grade_or_raise(grade_id, member_id)
        problem = self.problem_repo.get_by_id(grade.problem_id)
        exam_id = problem.exam_id
        data = request.model_dump(exclude_unset=True)
        updates: dict = {"method": GradeMethod.HUMAN}

        if "rubric_breakdown" in data and data["rubric_breakdown"] is not None:
            rubrics = self.rubric_repo.list_by_problem(grade.problem_id)
            rubric_map = {r.rubric_id: r for r in rubrics}
            updates["score"] = sum(
                rubric_map[item["rubric_id"]].allocated_score
                for item in data["rubric_breakdown"]
                if item["satisfied"] and item["rubric_id"] in rubric_map
            )
            updates["rubric_breakdown"] = data["rubric_breakdown"]
        elif "score" in data:
            updates["score"] = data["score"]

        if "comment" in data:
            updates["comment"] = data["comment"]

        self.grade_repo.update(grade, **updates)
        grade = self.grade_repo.get_by_id(grade_id)
        return self._build_grade_response(grade, problem, exam_id)

    def confirm_grade(self, grade_id: int, member_id: int) -> GradeResponse:
        grade = self._get_grade_or_raise(grade_id, member_id)
        problem = self.problem_repo.get_by_id(grade.problem_id)
        exam_id = problem.exam_id
        self.grade_repo.update(grade, status=GradeStatus.CONFIRMED)
        grade = self.grade_repo.get_by_id(grade_id)
        return self._build_grade_response(grade, problem, exam_id)

    def confirm_all_grades(self, problem_id: int, member_id: int) -> GradeBulkConfirmResponse:
        problem = self._get_problem_or_raise(problem_id, member_id)
        exam_id = problem.exam_id
        confirmed_count = self.grade_repo.confirm_all(problem_id)
        self.exam_repo.touch(exam_id)
        return GradeBulkConfirmResponse(confirmed_count=confirmed_count)


def _to_response(
    grade: Grade,
    student_name: str,
    student_no: str,
    max_score: int,
    rubrics: list[Rubric],
    ocr_result: OCRResult | None,
    model_answer_text: str | None,
) -> GradeResponse:
    breakdown = None
    if grade.rubric_breakdown:
        rubric_map = {r.rubric_id: r for r in rubrics}
        breakdown = [
            RubricResultItem(
                rubric_id=item["rubric_id"],
                text=rubric_map[item["rubric_id"]].text,
                allocated_score=rubric_map[item["rubric_id"]].allocated_score,
                satisfied=item["satisfied"],
            )
            for item in grade.rubric_breakdown
            if item["rubric_id"] in rubric_map
        ]

    return GradeResponse(
        grade_id=grade.grade_id,
        student_id=grade.student_id,
        student_name=student_name,
        student_no=student_no,
        score=grade.score,
        max_score=max_score,
        comment=grade.comment,
        status=grade.status,
        method=grade.method,
        rubric_breakdown=breakdown,
        ocr_text=ocr_result.text if ocr_result else None,
        marked_choice=ocr_result.marked_choice if ocr_result else None,
        model_answer_text=model_answer_text,
    )


def get_grade_service(db: Session = Depends(get_db)) -> GradeService:
    return GradeService(
        GradeRepository(db),
        ProblemRepository(db),
        ExamRepository(db),
        RubricRepository(db),
        OcrResultRepository(db),
        ModelAnswerRepository(db),
        StudentRepository(db),
        JobRepository(db),
    )
