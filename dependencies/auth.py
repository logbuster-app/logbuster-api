from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from domain.errors.users import UnauthorizedError
from utils.security import read_access_token

_bearer = HTTPBearer(auto_error=False)


def get_optional_user_id(
    request: Request,
    authorization: Annotated[HTTPAuthorizationCredentials | None, Security(_bearer)],
) -> UUID | None:
    headers = request.headers.getlist("Authorization")
    if not headers:
        return None
    if len(headers) != 1 or authorization is None:
        raise UnauthorizedError()
    return read_access_token(authorization.credentials)


OptionalUserId = Annotated[UUID | None, Depends(get_optional_user_id)]


def get_required_user_id(user_id: OptionalUserId) -> UUID:
    if user_id is None:
        raise UnauthorizedError()
    return user_id


RequiredUserId = Annotated[UUID, Depends(get_required_user_id)]
