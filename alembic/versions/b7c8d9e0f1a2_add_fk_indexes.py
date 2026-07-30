"""add fk indexes

Revision ID: b7c8d9e0f1a2
Revises: a3b4c5d6e7f8
Create Date: 2026-07-30 00:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

revision: str = "b7c8d9e0f1a2"
down_revision: str | None = "a3b4c5d6e7f8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# PostgreSQL은 FK 제약조건에 인덱스를 자동 생성하지 않는다.
# 아래 컬럼들은 조회 필터/조인 대상이면서 기존 PK·UNIQUE 인덱스로 커버되지 않는다.
#
# 의도적으로 제외한 FK (선두 컬럼이거나 unique라 이미 커버됨):
#   student.exam_id            → UNIQUE(exam_id, student_no)
#   grade.problem_id           → UNIQUE(problem_id, student_id)
#   answer_region.answer_sheet_id → UNIQUE(answer_sheet_id, problem_id, layout_mode)
#   ocr_result.answer_region_id, model_answer.problem_id → unique=True
INDEXES: list[tuple[str, str, str]] = [
    # (index_name, table, column)
    ("ix_exam_member_id", "exam", "member_id"),
    ("ix_problem_exam_id", "problem", "exam_id"),
    ("ix_rubric_problem_id", "rubric", "problem_id"),
    ("ix_grade_student_id", "grade", "student_id"),
    ("ix_answer_region_problem_id", "answer_region", "problem_id"),
    # 기존 uq_answer_sheet_exam_student는 부분 인덱스(WHERE student_id IS NOT NULL)라
    # 미매칭 시트(student_id IS NULL) 조회에는 사용되지 않는다.
    ("ix_answer_sheet_exam_id", "answer_sheet", "exam_id"),
    ("ix_answer_sheet_student_id", "answer_sheet", "student_id"),
    # job은 읽기 필터는 없지만 exam/problem/answer_sheet 삭제 시
    # ON DELETE SET NULL 처리를 위해 참조 행을 찾아야 한다.
    ("ix_job_exam_id", "job", "exam_id"),
    ("ix_job_problem_id", "job", "problem_id"),
    ("ix_job_answer_sheet_id", "job", "answer_sheet_id"),
]


def upgrade() -> None:
    for name, table, column in INDEXES:
        op.create_index(name, table, [column])


def downgrade() -> None:
    for name, table, _ in reversed(INDEXES):
        op.drop_index(name, table_name=table)
