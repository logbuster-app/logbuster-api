from typing import Annotated

from fastapi import Depends, Header

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
                "localStorage (SPEC-API-00, RN-03). Preenche viewer_interactions."
            ),
        ),
    ] = None,
) -> str | None:
    """Header opcional; valor em branco é tratado como ausente."""
    if x_visitor_id is None:
        return None
    return x_visitor_id.strip() or None


OptionalVisitorIdDep = Annotated[str | None, Depends(get_optional_visitor_id)]
