from typing import Annotated

from fastapi import Depends, Header

from domain.errors.reviews import MissingVisitorIdError

VISITOR_HEADER = "X-Visitor-Id"
MAX_VISITOR_ID_LENGTH = 64


def get_optional_visitor_id(
    x_visitor_id: Annotated[
        str | None,
        Header(
            alias=VISITOR_HEADER,
            max_length=MAX_VISITOR_ID_LENGTH,
            description=(
                "UUID do visitante anônimo, gerado pelo navegador e salvo em "
                "localStorage (SPEC-API-00, RN-03). Opcional nas leituras, onde "
                "preenche viewer_interactions; obrigatório para votar."
            ),
        ),
    ] = None,
) -> str | None:
    """Header opcional; valor em branco é tratado como ausente."""
    if x_visitor_id is None:
        return None
    return x_visitor_id.strip() or None


OptionalVisitorIdDep = Annotated[str | None, Depends(get_optional_visitor_id)]


def get_required_visitor_id(visitor_id: OptionalVisitorIdDep) -> str:
    """Header obrigatório: ausente ou em branco gera 400 BAD_REQUEST."""
    if visitor_id is None:
        raise MissingVisitorIdError()
    return visitor_id


RequiredVisitorIdDep = Annotated[str, Depends(get_required_visitor_id)]
