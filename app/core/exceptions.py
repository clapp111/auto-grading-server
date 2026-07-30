class EmailAlreadyExistsError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class InvalidCurrentPasswordError(Exception):
    pass


class UnauthorizedException(Exception):
    pass


class JobNotFoundError(Exception):
    pass


class ExamNotFoundError(Exception):
    pass


class ProblemNotFoundError(Exception):
    pass


class ModelAnswerNotFoundError(Exception):
    pass


class RubricNotFoundError(Exception):
    pass


class AnswerSheetNotFoundError(Exception):
    pass


class AnswerRegionNotFoundError(Exception):
    pass


class OcrResultNotFoundError(Exception):
    pass


class StudentNotFoundError(Exception):
    pass


class GradeNotFoundError(Exception):
    pass


class ExamStepConflictError(Exception):
    pass


class AutoGradeUnsupportedError(Exception):
    pass


class MemberNotFoundError(Exception):
    pass


class InvitationNotFoundError(Exception):
    pass


class SelfInvitationError(Exception):
    pass


class AlreadyExamMemberError(Exception):
    pass


class InvitationAlreadyRespondedError(Exception):
    pass


class InvitationAlreadyPendingError(Exception):
    pass


class ExamOwnerRequiredError(Exception):
    pass
