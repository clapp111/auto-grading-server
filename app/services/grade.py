from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.exceptions import (
    AutoGradeUnsupportedError,
    ExamNotFoundError,
    GradeNotFoundError,
    ProblemNotFoundError,
    StudentNotFoundError,
)
from app.db.session import get_db
from app.enums.grade_method import GradeMethod
from app.enums.grade_status import GradeStatus
from app.enums.job_type import JobType
from app.enums.problem_type import ProblemType
from app.models.grade import Grade
from app.models.ocr_result import OCRResult
from app.models.rubric import Rubric
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
    GradeCreateRequest,
    GradeResponse,
    GradeUpdateRequest,
    GradingProgressResponse,
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

    # ===========================================================================
    # ============================= 주요 서비스 기능 =============================
    # ===========================================================================

    def get_grading_progress(
        self, exam_id: int, member_id: int
    ) -> GradingProgressResponse:
        """문제별 채점 진행 현황을 조회한다.

        문제마다 확정된 채점 수를 학생 수 대비 비율(percent)로 집계하고, 전체 확정/가능
        건수를 함께 반환한다.

        Args:
            exam_id: 대상 시험 ID
            member_id: 요청한 사용자 ID

        Returns:
            문제별 진행 항목과 전체 확정/가능 건수 요약

        Raises:
            ExamNotFoundError: 시험이 없거나 접근 권한이 없는 경우
        """
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
            items.append(
                ProblemGradingItem(
                    problem_id=problem.problem_id,
                    label=problem.label,
                    type=problem.type,
                    max_score=problem.max_score,
                    confirmed_count=confirmed,
                    total_count=student_count,
                    percent=percent,
                )
            )

        return GradingProgressResponse(
            confirmed_count=total_confirmed,
            total_count=total_possible,
            problems=items,
        )

    def run_grade(
        self, exam_id: int, problem_id: int, member_id: int
    ) -> JobStartedResponse:
        """서술형·코딩 문제의 LLM 채점 잡을 생성해 비동기로 실행한다.

        객관식·단답형은 자동 채점을 지원하지 않으므로 거부한다.

        Args:
            exam_id: 대상 시험 ID
            problem_id: 채점할 문제 ID
            member_id: 요청한 사용자 ID

        Returns:
            시작된 잡의 ID와 상태

        Raises:
            ExamNotFoundError: 시험이 없거나 접근 권한이 없는 경우
            ProblemNotFoundError: 문제가 없거나 접근 권한이 없는 경우
            AutoGradeUnsupportedError: 객관식·단답형처럼 자동 채점을 지원하지 않는 유형인 경우
        """
        from app.workers.grade_tasks import run_llm_grade

        self._get_exam_or_raise(exam_id, member_id)
        problem = self._get_problem_or_raise(problem_id, member_id)

        if problem.type not in _LLM_TYPES:
            raise AutoGradeUnsupportedError()

        job = self.job_repo.create(
            exam_id=exam_id,
            problem_id=problem_id,
            type=JobType.LLM_GRADE,
            requested_by_member_id=member_id,
            input_json={
                "scope": {"examId": exam_id, "problemId": problem_id},
                "source": {
                    "trigger": "api",
                    "endpoint": f"/api/v1/exams/{exam_id}/problems/{problem_id}/grade/run",
                },
            },
        )

        run_llm_grade.delay(job.job_id)

        self.exam_repo.touch(exam_id)
        return JobStartedResponse(job_id=job.job_id, status=job.status)

    def list_grades(self, problem_id: int, member_id: int) -> list[GradeResponse]:
        """문제의 학생별 채점 결과 목록을 조회한다.

        각 채점에 학생 정보·루브릭·OCR 텍스트·모범답안을 합쳐 반환한다.

        Args:
            problem_id: 대상 문제 ID
            member_id: 요청한 사용자 ID

        Returns:
            학생·루브릭·OCR 정보가 포함된 채점 결과 목록

        Raises:
            ProblemNotFoundError: 문제가 없거나 접근 권한이 없는 경우
        """
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

    def update_grade(
        self, grade_id: int, member_id: int, request: GradeUpdateRequest
    ) -> GradeResponse:
        """채점 결과를 수동으로 수정한다.

        수정 시 채점 방식은 HUMAN으로 바뀐다. 루브릭 체크(rubric_breakdown)가 오면
        만족한 항목의 배점 합으로 점수를 다시 계산하고, 아니면 전달된 점수를 그대로 쓴다.

        Args:
            grade_id: 수정할 채점 결과 ID
            member_id: 요청한 사용자 ID
            request: 점수·루브릭 체크·코멘트 (미전송 필드는 무시)

        Returns:
            수정된 채점 결과

        Raises:
            GradeNotFoundError: 채점 결과가 없거나 접근 권한이 없는 경우
        """
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
        self.exam_repo.touch(exam_id)
        return self._build_grade_response(grade, problem, exam_id)

    def confirm_grade(self, grade_id: int, member_id: int) -> GradeResponse:
        """채점 결과 하나를 확정(CONFIRMED) 상태로 바꾼다.

        Args:
            grade_id: 확정할 채점 결과 ID
            member_id: 요청한 사용자 ID

        Returns:
            확정된 채점 결과

        Raises:
            GradeNotFoundError: 채점 결과가 없거나 접근 권한이 없는 경우
        """
        grade = self._get_grade_or_raise(grade_id, member_id)
        problem = self.problem_repo.get_by_id(grade.problem_id)
        exam_id = problem.exam_id
        self.grade_repo.update(grade, status=GradeStatus.CONFIRMED)
        grade = self.grade_repo.get_by_id(grade_id)
        self.exam_repo.touch(exam_id)
        return self._build_grade_response(grade, problem, exam_id)

    def confirm_all_grades(
        self, problem_id: int, member_id: int
    ) -> GradeBulkConfirmResponse:
        """문제의 모든 채점 결과를 한꺼번에 확정한다.

        Args:
            problem_id: 대상 문제 ID
            member_id: 요청한 사용자 ID

        Returns:
            확정된 채점 건수

        Raises:
            ProblemNotFoundError: 문제가 없거나 접근 권한이 없는 경우
        """
        problem = self._get_problem_or_raise(problem_id, member_id)
        exam_id = problem.exam_id
        confirmed_count = self.grade_repo.confirm_all(problem_id)
        self.exam_repo.touch(exam_id)
        return GradeBulkConfirmResponse(confirmed_count=confirmed_count)

    def delete_grades(self, problem_id: int, member_id: int) -> None:
        """문제의 모든 채점 결과를 삭제한다.

        Args:
            problem_id: 대상 문제 ID
            member_id: 요청한 사용자 ID

        Raises:
            ProblemNotFoundError: 문제가 없거나 접근 권한이 없는 경우
        """
        problem = self._get_problem_or_raise(problem_id, member_id)
        self.grade_repo.delete_by_problem(problem_id)
        self.exam_repo.touch(problem.exam_id)

    def create_grade(
        self,
        problem_id: int,
        student_id: int,
        member_id: int,
        request: GradeCreateRequest,
    ) -> GradeResponse:
        """학생의 채점 결과를 수동으로 생성하거나 점수를 갱신한다.

        같은 문제·학생의 채점이 이미 있으면 점수만 갱신하고, 없으면 새로 만든다.
        채점 방식은 HUMAN으로 기록한다.

        Args:
            problem_id: 대상 문제 ID
            student_id: 대상 학생 ID
            member_id: 요청한 사용자 ID
            request: 부여할 점수

        Returns:
            생성 또는 갱신된 채점 결과

        Raises:
            ProblemNotFoundError: 문제가 없거나 접근 권한이 없는 경우
            StudentNotFoundError: 학생이 없거나 해당 시험 소속이 아닌 경우
        """
        problem = self._get_problem_or_raise(problem_id, member_id)
        exam_id = problem.exam_id
        student = self.student_repo.get_by_id(student_id)
        if not student or student.exam_id != exam_id:
            raise StudentNotFoundError()

        existing = self.grade_repo.get_by_problem_and_student(problem_id, student_id)
        if existing:
            grade = self.grade_repo.update(existing, score=request.score)
        else:
            grade = self.grade_repo.create(
                problem_id=problem_id,
                student_id=student_id,
                score=request.score,
                method=GradeMethod.HUMAN,
            )
        self.exam_repo.touch(exam_id)
        return self._build_grade_response(grade, problem, exam_id)

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

    def _get_problem_or_raise(self, problem_id: int, member_id: int):
        """문제를 조회하고, 없거나 접근 권한이 없으면 예외를 던진다.

        Args:
            problem_id: 조회할 문제 ID
            member_id: 요청한 사용자 ID

        Returns:
            접근 가능한 문제

        Raises:
            ProblemNotFoundError: 문제가 없거나 접근 권한이 없는 경우
        """
        problem = self.problem_repo.get_by_id(problem_id)
        if not problem:
            raise ProblemNotFoundError()
        exam = self.exam_repo.get_accessible(problem.exam_id, member_id)
        if not exam:
            raise ProblemNotFoundError()
        return problem

    def _get_grade_or_raise(self, grade_id: int, member_id: int) -> Grade:
        """채점 결과를 조회하고, 없거나 접근 권한이 없으면 예외를 던진다.

        Args:
            grade_id: 조회할 채점 결과 ID
            member_id: 요청한 사용자 ID

        Returns:
            접근 가능한 채점 결과

        Raises:
            GradeNotFoundError: 채점 결과·문제가 없거나 접근 권한이 없는 경우
        """
        grade = self.grade_repo.get_by_id(grade_id)
        if not grade:
            raise GradeNotFoundError()
        problem = self.problem_repo.get_by_id(grade.problem_id)
        if not problem:
            raise GradeNotFoundError()
        exam = self.exam_repo.get_accessible(problem.exam_id, member_id)
        if not exam:
            raise GradeNotFoundError()
        return grade

    def _build_grade_response(
        self, grade: Grade, problem, exam_id: int
    ) -> GradeResponse:
        """채점 결과에 학생·루브릭·OCR·모범답안을 합쳐 응답으로 변환한다.

        Args:
            grade: 변환할 채점 결과
            problem: 채점 대상 문제
            exam_id: 갱신 시각을 찍을 시험 ID

        Returns:
            부가 정보가 포함된 채점 결과 응답
        """
        student = self.student_repo.get_by_id(grade.student_id)
        rubrics = self.rubric_repo.list_by_problem(grade.problem_id)
        ocr_map = self.ocr_result_repo.map_by_problem(grade.problem_id)
        model_answer = self.model_answer_repo.get_by_problem_id(grade.problem_id)
        model_answer_text = model_answer.model_answer_text if model_answer else None
        return _to_response(
            grade,
            student.name,
            student.student_no,
            problem.max_score,
            rubrics,
            ocr_map.get(grade.student_id),
            model_answer_text,
        )


def _to_response(
    grade: Grade,
    student_name: str,
    student_no: str,
    max_score: int,
    rubrics: list[Rubric],
    ocr_result: OCRResult | None,
    model_answer_text: str | None,
) -> GradeResponse:
    """채점 결과와 부가 정보를 합쳐 응답 스키마로 변환한다.

    루브릭 체크(rubric_breakdown)가 있으면 각 항목을 루브릭 텍스트·배점과 함께 복원한다.
    `result.py`의 학생 상세 조회에서도 재사용한다.

    Args:
        grade: 변환할 채점 결과
        student_name: 학생 이름
        student_no: 학생 학번
        max_score: 문제 배점
        rubrics: 문제의 채점 기준 목록
        ocr_result: 학생 답안의 OCR 결과 (없으면 `None`)
        model_answer_text: 모범답안 텍스트 (없으면 `None`)

    Returns:
        학생·점수·루브릭·OCR·모범답안이 포함된 채점 응답
    """
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
