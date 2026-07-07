"""add ondelete cascade to all fks

Revision ID: f1a2b3c4d5e6
Revises: e5f6a7b8c9d0
Create Date: 2026-07-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# CASCADE: 부모 삭제 시 자식도 삭제
# SET NULL: 부모 삭제 시 nullable FK를 null로

def upgrade() -> None:
    # grade.problem_id → problem (CASCADE)
    op.drop_constraint('grade_problem_id_fkey', 'grade', type_='foreignkey')
    op.create_foreign_key('grade_problem_id_fkey', 'grade', 'problem', ['problem_id'], ['problem_id'], ondelete='CASCADE')

    # grade.student_id → student (CASCADE)
    op.drop_constraint('grade_student_id_fkey', 'grade', type_='foreignkey')
    op.create_foreign_key('grade_student_id_fkey', 'grade', 'student', ['student_id'], ['student_id'], ondelete='CASCADE')

    # ocr_result.answer_region_id → answer_region (CASCADE)
    op.drop_constraint('ocr_result_answer_region_id_fkey', 'ocr_result', type_='foreignkey')
    op.create_foreign_key('ocr_result_answer_region_id_fkey', 'ocr_result', 'answer_region', ['answer_region_id'], ['answer_region_id'], ondelete='CASCADE')

    # model_answer.problem_id → problem (CASCADE)
    op.drop_constraint('model_answer_problem_id_fkey', 'model_answer', type_='foreignkey')
    op.create_foreign_key('model_answer_problem_id_fkey', 'model_answer', 'problem', ['problem_id'], ['problem_id'], ondelete='CASCADE')

    # rubric.problem_id → problem (CASCADE)
    op.drop_constraint('rubric_problem_id_fkey', 'rubric', type_='foreignkey')
    op.create_foreign_key('rubric_problem_id_fkey', 'rubric', 'problem', ['problem_id'], ['problem_id'], ondelete='CASCADE')

    # answer_region.answer_sheet_id → answer_sheet (CASCADE)
    op.drop_constraint('answer_region_answer_sheet_id_fkey', 'answer_region', type_='foreignkey')
    op.create_foreign_key('answer_region_answer_sheet_id_fkey', 'answer_region', 'answer_sheet', ['answer_sheet_id'], ['answer_sheet_id'], ondelete='CASCADE')

    # answer_region.problem_id → problem (CASCADE)
    op.drop_constraint('answer_region_problem_id_fkey', 'answer_region', type_='foreignkey')
    op.create_foreign_key('answer_region_problem_id_fkey', 'answer_region', 'problem', ['problem_id'], ['problem_id'], ondelete='CASCADE')

    # problem.exam_id → exam (CASCADE)
    op.drop_constraint('problem_exam_id_fkey', 'problem', type_='foreignkey')
    op.create_foreign_key('problem_exam_id_fkey', 'problem', 'exam', ['exam_id'], ['exam_id'], ondelete='CASCADE')

    # student.exam_id → exam (CASCADE)
    op.drop_constraint('student_exam_id_fkey', 'student', type_='foreignkey')
    op.create_foreign_key('student_exam_id_fkey', 'student', 'exam', ['exam_id'], ['exam_id'], ondelete='CASCADE')

    # answer_sheet.exam_id → exam (CASCADE)
    op.drop_constraint('answer_sheet_exam_id_fkey', 'answer_sheet', type_='foreignkey')
    op.create_foreign_key('answer_sheet_exam_id_fkey', 'answer_sheet', 'exam', ['exam_id'], ['exam_id'], ondelete='CASCADE')

    # answer_sheet.student_id → student (SET NULL: 학생 삭제 시 답안지는 미매칭 상태로 남음)
    op.drop_constraint('answer_sheet_student_id_fkey', 'answer_sheet', type_='foreignkey')
    op.create_foreign_key('answer_sheet_student_id_fkey', 'answer_sheet', 'student', ['student_id'], ['student_id'], ondelete='SET NULL')

    # job.exam_id → exam (CASCADE)
    op.drop_constraint('job_exam_id_fkey', 'job', type_='foreignkey')
    op.create_foreign_key('job_exam_id_fkey', 'job', 'exam', ['exam_id'], ['exam_id'], ondelete='CASCADE')

    # job.problem_id → problem (SET NULL: nullable)
    op.drop_constraint('job_problem_id_fkey', 'job', type_='foreignkey')
    op.create_foreign_key('job_problem_id_fkey', 'job', 'problem', ['problem_id'], ['problem_id'], ondelete='SET NULL')

    # job.answer_sheet_id → answer_sheet (SET NULL: nullable)
    op.drop_constraint('job_answer_sheet_id_fkey', 'job', type_='foreignkey')
    op.create_foreign_key('job_answer_sheet_id_fkey', 'job', 'answer_sheet', ['answer_sheet_id'], ['answer_sheet_id'], ondelete='SET NULL')

    # job.retry_of_job_id → job (SET NULL: self-referential, nullable)
    op.drop_constraint('job_retry_of_job_id_fkey', 'job', type_='foreignkey')
    op.create_foreign_key('job_retry_of_job_id_fkey', 'job', 'job', ['retry_of_job_id'], ['job_id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('job_retry_of_job_id_fkey', 'job', type_='foreignkey')
    op.create_foreign_key('job_retry_of_job_id_fkey', 'job', 'job', ['retry_of_job_id'], ['job_id'])

    op.drop_constraint('job_answer_sheet_id_fkey', 'job', type_='foreignkey')
    op.create_foreign_key('job_answer_sheet_id_fkey', 'job', 'answer_sheet', ['answer_sheet_id'], ['answer_sheet_id'])

    op.drop_constraint('job_problem_id_fkey', 'job', type_='foreignkey')
    op.create_foreign_key('job_problem_id_fkey', 'job', 'problem', ['problem_id'], ['problem_id'])

    op.drop_constraint('job_exam_id_fkey', 'job', type_='foreignkey')
    op.create_foreign_key('job_exam_id_fkey', 'job', 'exam', ['exam_id'], ['exam_id'])

    op.drop_constraint('answer_sheet_student_id_fkey', 'answer_sheet', type_='foreignkey')
    op.create_foreign_key('answer_sheet_student_id_fkey', 'answer_sheet', 'student', ['student_id'], ['student_id'])

    op.drop_constraint('answer_sheet_exam_id_fkey', 'answer_sheet', type_='foreignkey')
    op.create_foreign_key('answer_sheet_exam_id_fkey', 'answer_sheet', 'exam', ['exam_id'], ['exam_id'])

    op.drop_constraint('student_exam_id_fkey', 'student', type_='foreignkey')
    op.create_foreign_key('student_exam_id_fkey', 'student', 'exam', ['exam_id'], ['exam_id'])

    op.drop_constraint('problem_exam_id_fkey', 'problem', type_='foreignkey')
    op.create_foreign_key('problem_exam_id_fkey', 'problem', 'exam', ['exam_id'], ['exam_id'])

    op.drop_constraint('answer_region_problem_id_fkey', 'answer_region', type_='foreignkey')
    op.create_foreign_key('answer_region_problem_id_fkey', 'answer_region', 'problem', ['problem_id'], ['problem_id'])

    op.drop_constraint('answer_region_answer_sheet_id_fkey', 'answer_region', type_='foreignkey')
    op.create_foreign_key('answer_region_answer_sheet_id_fkey', 'answer_region', 'answer_sheet', ['answer_sheet_id'], ['answer_sheet_id'])

    op.drop_constraint('rubric_problem_id_fkey', 'rubric', type_='foreignkey')
    op.create_foreign_key('rubric_problem_id_fkey', 'rubric', 'problem', ['problem_id'], ['problem_id'])

    op.drop_constraint('model_answer_problem_id_fkey', 'model_answer', type_='foreignkey')
    op.create_foreign_key('model_answer_problem_id_fkey', 'model_answer', 'problem', ['problem_id'], ['problem_id'])

    op.drop_constraint('ocr_result_answer_region_id_fkey', 'ocr_result', type_='foreignkey')
    op.create_foreign_key('ocr_result_answer_region_id_fkey', 'ocr_result', 'answer_region', ['answer_region_id'], ['answer_region_id'])

    op.drop_constraint('grade_student_id_fkey', 'grade', type_='foreignkey')
    op.create_foreign_key('grade_student_id_fkey', 'grade', 'student', ['student_id'], ['student_id'])

    op.drop_constraint('grade_problem_id_fkey', 'grade', type_='foreignkey')
    op.create_foreign_key('grade_problem_id_fkey', 'grade', 'problem', ['problem_id'], ['problem_id'])
