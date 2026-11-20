from domain.errors.base import AppError, NotFoundError


class UnauthorizedError(AppError):
    status_code = 401
    code = "UNAUTHORIZED"
    message = "Autenticação inválida ou ausente."


class EmailConflictError(AppError):
    status_code = 409
    code = "CONFLICT"
    message = "Este e-mail já está cadastrado."


class UserNotFoundError(NotFoundError):
    message = "Usuário não encontrado."


class AuthConfigurationError(AppError):
    status_code = 503
    code = "SERVICE_UNAVAILABLE"
    message = "Autenticação temporariamente indisponível."


class ProfileImageNotFoundError(NotFoundError):
    message = "Imagem de perfil não encontrada."


class ProfileImageTooLargeError(AppError):
    status_code = 413
    code = "PAYLOAD_TOO_LARGE"
    message = "A imagem deve ter até 8 MiB e 4096 pixels em cada dimensão."


class UnsupportedProfileImageTypeError(AppError):
    status_code = 415
    code = "UNSUPPORTED_MEDIA_TYPE"
    message = "Envie uma imagem JPEG, PNG ou WebP com Content-Type correspondente."


class InvalidProfileImageError(AppError):
    status_code = 422
    code = "VALIDATION_ERROR"
    message = "Envie uma imagem válida e sem animação."
