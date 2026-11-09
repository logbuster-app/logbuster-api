from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    field: str
    issue: str


class ErrorBody(BaseModel):
    code: str = Field(examples=["VALIDATION_ERROR"])
    message: str = Field(examples=["Os dados enviados são inválidos."])
    details: list[ErrorDetail] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    """Envelope único de erro (SPEC-API-00, §4.3)."""

    error: ErrorBody
