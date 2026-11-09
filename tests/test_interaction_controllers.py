from uuid import uuid4

import pytest

from domain.enums import ReviewInteractionType
from domain.errors.reviews import ReviewNotFoundError
from domain.schemas.interactions import InteractionToggleResponse
from domain.schemas.reviews import ReviewCounts

VISITOR = {"X-Visitor-Id": "550e8400-e29b-41d4-a716-446655440000"}


def url(review_id):
    return f"/api/v1/reviews/{review_id}/interactions"


def toggle_response(review_id, active=True):
    return InteractionToggleResponse(
        review_id=review_id,
        type=ReviewInteractionType.WELL_ARGUED,
        active=active,
        counts=ReviewCounts(like=4, spoiler=0, well_argued=10 if active else 9),
        viewer_interactions=["well_argued"] if active else [],
    )


def assert_error(response, status, code):
    assert response.status_code == status
    body = response.json()
    assert set(body) == {"error"} and body["error"]["code"] == code
    return body["error"]


def test_toggle_returns_200_with_spec_contract(client, interaction_service):
    review_id = uuid4()
    interaction_service.toggle.return_value = toggle_response(review_id)

    response = client.post(
        url(review_id), json={"type": "well_argued"}, headers=VISITOR
    )

    assert response.status_code == 200
    assert response.json() == {
        "review_id": str(review_id),
        "type": "well_argued",
        "active": True,
        "counts": {"like": 4, "spoiler": 0, "well_argued": 10},
        "viewer_interactions": ["well_argued"],
    }
    called_id, payload, visitor = interaction_service.toggle.call_args.args
    assert called_id == review_id
    assert payload.type == ReviewInteractionType.WELL_ARGUED
    assert visitor == VISITOR["X-Visitor-Id"]


@pytest.mark.parametrize("kind", ["like", "spoiler", "well_argued"])
def test_all_spec_types_are_accepted(client, interaction_service, kind):
    review_id = uuid4()
    interaction_service.toggle.return_value = toggle_response(review_id)
    response = client.post(url(review_id), json={"type": kind}, headers=VISITOR)
    assert response.status_code == 200


def test_visitor_header_is_trimmed(client, interaction_service):
    review_id = uuid4()
    interaction_service.toggle.return_value = toggle_response(review_id)
    client.post(url(review_id), json={"type": "like"}, headers={"X-Visitor-Id": " V1 "})
    assert interaction_service.toggle.call_args.args[2] == "V1"


@pytest.mark.parametrize("headers", [{}, {"X-Visitor-Id": ""}, {"X-Visitor-Id": "  "}])
def test_missing_visitor_returns_400(client, interaction_service, headers):
    response = client.post(url(uuid4()), json={"type": "like"}, headers=headers)
    error = assert_error(response, 400, "BAD_REQUEST")
    assert error["message"] == (
        "O header X-Visitor-Id é obrigatório para registrar interações."
    )
    assert error["details"] == [
        {"field": "X-Visitor-Id", "issue": "Header ausente ou vazio."}
    ]
    interaction_service.toggle.assert_not_called()


def test_missing_visitor_wins_over_invalid_body(client, interaction_service):
    response = client.post(url(uuid4()), json={"type": "dislike"})
    assert_error(response, 400, "BAD_REQUEST")


def test_too_long_visitor_returns_400(client, interaction_service):
    response = client.post(
        url(uuid4()), json={"type": "like"}, headers={"X-Visitor-Id": "x" * 65}
    )
    assert_error(response, 400, "BAD_REQUEST")
    interaction_service.toggle.assert_not_called()


@pytest.mark.parametrize(
    "body",
    [
        {"type": "dislike"},
        {"type": "LIKE"},
        {"type": "bem_argumentada"},
        {"type": None},
        {},
        {"type": "like", "extra": True},
    ],
)
def test_invalid_type_returns_422(client, interaction_service, body):
    response = client.post(url(uuid4()), json=body, headers=VISITOR)
    error = assert_error(response, 422, "VALIDATION_ERROR")
    if body.get("type") not in (None, "like"):
        assert error["message"] == (
            "O tipo de interação deve ser like, spoiler ou well_argued."
        )
    interaction_service.toggle.assert_not_called()


def test_missing_review_returns_404(client, interaction_service):
    interaction_service.toggle.side_effect = ReviewNotFoundError()
    response = client.post(url(uuid4()), json={"type": "like"}, headers=VISITOR)
    error = assert_error(response, 404, "NOT_FOUND")
    assert error["message"] == "Avaliação não encontrada."


def test_malformed_review_id_returns_422(client, interaction_service):
    response = client.post(url("abc"), json={"type": "like"}, headers=VISITOR)
    error = assert_error(response, 422, "VALIDATION_ERROR")
    assert error["details"][0]["field"] == "review_id"
    interaction_service.toggle.assert_not_called()


def test_cors_preflight_allows_visitor_header_on_post(client):
    response = client.options(
        url(uuid4()),
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type, x-visitor-id",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "x-visitor-id" in response.headers["access-control-allow-headers"].lower()


def test_openapi_documents_errors(client):
    operation = client.get("/api/openapi.json").json()["paths"][
        "/api/v1/reviews/{review_id}/interactions"
    ]["post"]
    assert set(operation["responses"]) >= {"200", "400", "404", "422"}
    assert {(p["name"], p["in"]) for p in operation["parameters"]} == {
        ("review_id", "path"),
        ("X-Visitor-Id", "header"),
    }
