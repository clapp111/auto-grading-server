from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.exceptions import ExamNotFoundError, StudentNotFoundError
from app.db.session import get_db
from app.enums.grade_status import GradeStatus
from app.repositories.exam import ExamRepository
from app.repositories.model_answer import ModelAnswerRepository
from app.repositories.ocr_result import OcrResultRepository
from app.repositories.problem import ProblemRepository
from app.repositories.result import ResultRepository
from app.repositories.rubric import RubricRepository
from app.repositories.student import StudentRepository
from app.schemas.result import (
    ExamResultResponse,
    ExamStatisticsResponse,
    ProblemHeader,
    ProblemScoreItem,
    ProblemStatItem,
    ScoreBandItem,
    StudentDetailResultResponse,
    StudentScoreItem,
)
from app.services.grade import _to_response


class ResultService:
    def __init__(
        self,
        result_repo: ResultRepository,
        problem_repo: ProblemRepository,
        exam_repo: ExamRepository,
        student_repo: StudentRepository,
        rubric_repo: RubricRepository,
        ocr_result_repo: OcrResultRepository,
        model_answer_repo: ModelAnswerRepository,
    ):
        self.result_repo = result_repo
        self.problem_repo = problem_repo
        self.exam_repo = exam_repo
        self.student_repo = student_repo
        self.rubric_repo = rubric_repo
        self.ocr_result_repo = ocr_result_repo
        self.model_answer_repo = model_answer_repo

    def _get_exam_or_raise(self, exam_id: int, member_id: int):
        exam = self.exam_repo.get_accessible(exam_id, member_id)
        if not exam:
            raise ExamNotFoundError()
        return exam

    def _get_student_or_raise(self, student_id: int, exam_id: int):
        student = self.student_repo.get_by_id(student_id)
        if not student or student.exam_id != exam_id:
            raise StudentNotFoundError()
        return student

    def get_exam_results(self, exam_id: int, member_id: int) -> ExamResultResponse:
        exam = self._get_exam_or_raise(exam_id, member_id)
        problems = self.problem_repo.list_by_exam(exam_id)
        students = self.result_repo.list_students_by_exam(exam_id)
        grade_map = self.result_repo.map_grades_by_exam(exam_id)

        max_total_score = sum(p.max_score for p in problems)
        problem_headers = [
            ProblemHeader(problem_id=p.problem_id, label=p.label, max_score=p.max_score)
            for p in problems
        ]

        student_items = []
        for student in students:
            total_score = 0
            problem_scores = []
            for p in problems:
                grade = grade_map.get((p.problem_id, student.student_id))
                if grade and grade.status == GradeStatus.CONFIRMED:
                    total_score += grade.score
                problem_scores.append(ProblemScoreItem(
                    problem_id=p.problem_id,
                    score=grade.score if grade else None,
                    status=grade.status if grade else None,
                ))
            student_items.append(StudentScoreItem(
                student_id=student.student_id,
                name=student.name,
                student_no=student.student_no,
                total_score=total_score,
                max_total_score=max_total_score,
                problem_scores=problem_scores,
            ))

        return ExamResultResponse(
            exam_id=exam.exam_id,
            title=exam.name,    # DB에는 name 컬럼이지만, API 스펙에서는 title로 노출
            problems=problem_headers,
            students=student_items,
        )

    def get_statistics(self, exam_id: int, member_id: int) -> ExamStatisticsResponse:
        self._get_exam_or_raise(exam_id, member_id)
        problems = self.problem_repo.list_by_exam(exam_id)
        students = self.result_repo.list_students_by_exam(exam_id)
        grade_map = self.result_repo.map_grades_by_exam(exam_id)

        max_total_score = sum(p.max_score for p in problems)
        problem_count = len(problems)

        if problem_count == 0:
            return ExamStatisticsResponse(
                total_students=len(students),
                fully_graded_count=0,
                average_score=0.0,
                highest_score=0,
                lowest_score=0,
                score_distribution=[],
                problem_stats=[],
            )

        fully_graded_totals: list[int] = []
        for student in students:
            confirmed = [
                grade_map[(p.problem_id, student.student_id)]
                for p in problems
                if (p.problem_id, student.student_id) in grade_map
                and grade_map[(p.problem_id, student.student_id)].status == GradeStatus.CONFIRMED
            ]
            if len(confirmed) == problem_count:
                fully_graded_totals.append(sum(g.score for g in confirmed))

        if fully_graded_totals:
            average_score = round(sum(fully_graded_totals) / len(fully_graded_totals), 2)
            highest_score = max(fully_graded_totals)
            lowest_score = min(fully_graded_totals)
        else:
            average_score = 0.0
            highest_score = 0
            lowest_score = 0

        problem_stats = []
        for p in problems:
            confirmed_scores = [
                grade_map[(p.problem_id, s.student_id)].score
                for s in students
                if (p.problem_id, s.student_id) in grade_map
                and grade_map[(p.problem_id, s.student_id)].status == GradeStatus.CONFIRMED
            ]
            avg = round(sum(confirmed_scores) / len(confirmed_scores), 2) if confirmed_scores else 0.0
            problem_stats.append(ProblemStatItem(
                problem_id=p.problem_id,
                label=p.label,
                max_score=p.max_score,
                average_score=avg,
            ))

        return ExamStatisticsResponse(
            total_students=len(students),
            fully_graded_count=len(fully_graded_totals),
            average_score=average_score,
            highest_score=highest_score,
            lowest_score=lowest_score,
            score_distribution=_build_distribution(fully_graded_totals, max_total_score),
            problem_stats=problem_stats,
        )

    def export_results_csv(self, exam_id: int, member_id: int) -> tuple[bytes, str]:
        """성적 CSV를 (bytes, filename) 형태로 반환. 인코딩은 utf-8-sig(Excel BOM 포함)."""
        import csv
        import io

        result = self.get_exam_results(exam_id, member_id)

        buf = io.StringIO()
        writer = csv.writer(buf)

        header = ["학번", "이름"] + [f"{p.label}({p.max_score})" for p in result.problems] + ["총점"]
        writer.writerow(header)

        for student in result.students:
            score_cells = [
                str(ps.score) if ps.score is not None else ""
                for ps in student.problem_scores
            ]
            writer.writerow([student.student_no, student.name] + score_cells + [student.total_score])

        content = buf.getvalue().encode("utf-8-sig")
        filename = f"exam_{exam_id}_results.csv"
        return content, filename

    def get_student_result(self, student_id: int, exam_id: int, member_id: int) -> StudentDetailResultResponse:
        exam = self._get_exam_or_raise(exam_id, member_id)
        student = self._get_student_or_raise(student_id, exam_id)

        grades = self.result_repo.list_grades_by_student_exam(student_id, exam_id)
        problems = self.problem_repo.list_by_exam(exam_id)
        problem_map = {p.problem_id: p for p in problems}
        max_total_score = sum(p.max_score for p in problems)
        total_score = sum(g.score for g in grades if g.status == GradeStatus.CONFIRMED)

        problem_ids = [g.problem_id for g in grades]
        model_answer_map = self.model_answer_repo.map_by_problem_ids(problem_ids)
        rubric_map = self.rubric_repo.map_by_problem_ids(problem_ids)

        ocr_results = self.ocr_result_repo.list_by_student(student_id, exam.layout_mode)
        ocr_map = {region.problem_id: ocr for ocr, region in ocr_results}

        grade_responses = []
        for grade in grades:
            rubrics = rubric_map.get(grade.problem_id, [])
            ma = model_answer_map.get(grade.problem_id)
            problem = problem_map[grade.problem_id]
            grade_responses.append(
                _to_response(grade, student.name, student.student_no, problem.max_score, rubrics, ocr_map.get(grade.problem_id), ma.model_answer_text if ma else None)
            )

        return StudentDetailResultResponse(
            student_id=student.student_id,
            name=student.name,
            student_no=student.student_no,
            total_score=total_score,
            max_total_score=max_total_score,
            grades=grade_responses,
        )


def _build_distribution(totals: list[int], max_total: int) -> list[ScoreBandItem]:
    if not totals or max_total == 0:
        return []
    band_size = max(1, max_total // 5)
    items = []
    for i in range(5):
        lo = i * band_size
        hi = lo + band_size - 1 if i < 4 else max_total
        items.append(ScoreBandItem(
            range_label=f"{lo}~{hi}",
            count=sum(1 for s in totals if lo <= s <= hi),
        ))
    return items


def get_result_service(db: Session = Depends(get_db)) -> ResultService:
    return ResultService(
        ResultRepository(db),
        ProblemRepository(db),
        ExamRepository(db),
        StudentRepository(db),
        RubricRepository(db),
        OcrResultRepository(db),
        ModelAnswerRepository(db),
    )
