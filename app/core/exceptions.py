class EmailAlreadyExistsError(Exception):
    pass


class InvalidCredentialsError(Exception):
    pass


class UnauthorizedException(Exception):
    pass


class JobNotFoundError(Exception):
    pass
