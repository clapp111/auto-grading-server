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

    # ===========================================================================
    # ============================= 주요 서비스 기능 =============================
    # ===========================================================================

    def get_exam_results(self, exam_id: int, member_id: int) -> ExamResultResponse:
        """시험의 학생 × 문제 점수표를 조회한다.

        문제별 헤더와 학생별 점수 행을 구성하며, 확정(CONFIRMED)된 채점만 총점에 더한다.

        Args:
            exam_id: 대상 시험 ID
            member_id: 요청한 사용자 ID

        Returns:
            문제 헤더와 학생별 점수가 담긴 결과표

        Raises:
            ExamNotFoundError: 시험이 없거나 접근 권한이 없는 경우
        """
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
                problem_scores.append(
                    ProblemScoreItem(
                        problem_id=p.problem_id,
                        score=grade.score if grade else None,
                        status=grade.status if grade else None,
                    )
                )
            student_items.append(
                StudentScoreItem(
                    student_id=student.student_id,
                    name=student.name,
                    student_no=student.student_no,
                    total_score=total_score,
                    max_total_score=max_total_score,
                    problem_scores=problem_scores,
                )
            )

        return ExamResultResponse(
            exam_id=exam.exam_id,
            title=exam.name,  # DB에는 name 컬럼이지만, API 스펙에서는 title로 노출
            problems=problem_headers,
            students=student_items,
        )

    def get_statistics(self, exam_id: int, member_id: int) -> ExamStatisticsResponse:
        """시험의 성적 통계를 집계한다.

        모든 문제가 확정된 학생만 평균·최고·최저 점수 집계 대상으로 삼고, 점수 분포와
        문제별 평균을 함께 계산한다. 문제가 없으면 빈 통계를 반환한다.

        Args:
            exam_id: 대상 시험 ID
            member_id: 요청한 사용자 ID

        Returns:
            평균·최고·최저·점수 분포·문제별 평균이 담긴 통계

        Raises:
            ExamNotFoundError: 시험이 없거나 접근 권한이 없는 경우
        """
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
                and grade_map[(p.problem_id, student.student_id)].status
                == GradeStatus.CONFIRMED
            ]
            if len(confirmed) == problem_count:
                fully_graded_totals.append(sum(g.score for g in confirmed))

        if fully_graded_totals:
            average_score = round(
                sum(fully_graded_totals) / len(fully_graded_totals), 2
            )
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
                and grade_map[(p.problem_id, s.student_id)].status
                == GradeStatus.CONFIRMED
            ]
            avg = (
                round(sum(confirmed_scores) / len(confirmed_scores), 2)
                if confirmed_scores
                else 0.0
            )
            problem_stats.append(
                ProblemStatItem(
                    problem_id=p.problem_id,
                    label=p.label,
                    max_score=p.max_score,
                    average_score=avg,
                )
            )

        return ExamStatisticsResponse(
            total_students=len(students),
            fully_graded_count=len(fully_graded_totals),
            average_score=average_score,
            highest_score=highest_score,
            lowest_score=lowest_score,
            score_distribution=_build_distribution(
                fully_graded_totals, max_total_score
            ),
            problem_stats=problem_stats,
        )

    def export_results_csv(self, exam_id: int, member_id: int) -> tuple[bytes, str]:
        """시험 성적표를 CSV 바이트로 내보낸다.

        Excel에서 한글이 깨지지 않도록 utf-8-sig(BOM 포함)로 인코딩한다.

        Args:
            exam_id: 대상 시험 ID
            member_id: 요청한 사용자 ID

        Returns:
            CSV 바이트와 파일명의 튜플

        Raises:
            ExamNotFoundError: 시험이 없거나 접근 권한이 없는 경우
        """
        import csv
        import io

        result = self.get_exam_results(exam_id, member_id)

        buf = io.StringIO()
        writer = csv.writer(buf)

        header = (
            ["학번", "이름"]
            + [f"{p.label}({p.max_score})" for p in result.problems]
            + ["총점"]
        )
        writer.writerow(header)

        for student in result.students:
            score_cells = [
                str(ps.score) if ps.score is not None else ""
                for ps in student.problem_scores
            ]
            writer.writerow(
                [student.student_no, student.name] + score_cells + [student.total_score]
            )

        content = buf.getvalue().encode("utf-8-sig")
        filename = f"exam_{exam_id}_results.csv"
        return content, filename

    def get_student_result(
        self, student_id: int, exam_id: int, member_id: int
    ) -> StudentDetailResultResponse:
        """학생 한 명의 문제별 상세 채점 결과를 조회한다.

        각 채점에 루브릭·OCR·모범답안을 합쳐 담고, 확정된 채점만 총점에 더한다.

        Args:
            student_id: 대상 학생 ID
            exam_id: 대상 시험 ID
            member_id: 요청한 사용자 ID

        Returns:
            학생의 총점과 문제별 상세 채점 결과

        Raises:
            ExamNotFoundError: 시험이 없거나 접근 권한이 없는 경우
            StudentNotFoundError: 학생이 없거나 해당 시험 소속이 아닌 경우
        """
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
                _to_response(
                    grade,
                    student.name,
                    student.student_no,
                    problem.max_score,
                    rubrics,
                    ocr_map.get(grade.problem_id),
                    ma.model_answer_text if ma else None,
                )
            )

        return StudentDetailResultResponse(
            student_id=student.student_id,
            name=student.name,
            student_no=student.student_no,
            total_score=total_score,
            max_total_score=max_total_score,
            grades=grade_responses,
        )

    # ===========================================================================
    # ================================ 헬퍼 함수 ================================
    # ===========================================================================

    def _get_exam_or_raise(self, exam_id: int, member_id: int):
        """접근 가능한 시험을 조회하고, 없으면 예외를 던진다.

        Args:
            exam_id: 조회할 시험 ID
            member_id: 요청한 사용자 ID

        Returns:
            접근 가능한 시험

        Raises:
            ExamNotFoundError: 시험이 없거나 접근 권한이 없는 경우
        """
        exam = self.exam_repo.get_accessible(exam_id, member_id)
        if not exam:
            raise ExamNotFoundError()
        return exam

    def _get_student_or_raise(self, student_id: int, exam_id: int):
        """학생을 조회하고, 없거나 시험 소속이 아니면 예외를 던진다.

        Args:
            student_id: 조회할 학생 ID
            exam_id: 학생이 속해야 할 시험 ID

        Returns:
            해당 시험에 속한 학생

        Raises:
            StudentNotFoundError: 학생이 없거나 해당 시험 소속이 아닌 경우
        """
        student = self.student_repo.get_by_id(student_id)
        if not student or student.exam_id != exam_id:
            raise StudentNotFoundError()
        return student


def _build_distribution(totals: list[int], max_total: int) -> list[ScoreBandItem]:
    """총점 목록을 5개 점수 구간으로 나눠 분포를 만든다.

    최고점을 5등분한 구간별로 학생 수를 센다. 총점이 없거나 만점이 0이면 빈 목록을 반환한다.

    Args:
        totals: 집계 대상 학생들의 총점 목록
        max_total: 시험 만점

    Returns:
        점수 구간별 학생 수 목록
    """
    if not totals or max_total == 0:
        return []
    band_size = max(1, max_total // 5)
    items = []
    for i in range(5):
        lo = i * band_size
        hi = lo + band_size - 1 if i < 4 else max_total
        items.append(
            ScoreBandItem(
                range_label=f"{lo}~{hi}",
                count=sum(1 for s in totals if lo <= s <= hi),
            )
        )
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
