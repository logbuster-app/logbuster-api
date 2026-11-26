from datetime import UTC, datetime, timedelta
from io import BytesIO
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from dependencies.session import get_session
from domain.models.profile_image import ProfileImage
from domain.models.review import Review
from domain.models.user import User
from main import app
from utils.security import create_access_token, hash_password, verify_password

KEY = "test-key-used-only-in-the-test-suite"
PASSWORD = "uma-senha-de-teste"
REGISTER = "/api/v1/auth/register"
LOGIN = "/api/v1/auth/login"
ME = "/api/v1/auth/me"
USERS = "/api/v1/users"


@pytest.fixture
def user():
    return User(
        id=uuid4(),
        display_name="Pessoa cinéfila",
        email="cinefila@example.com",
        password_hash=hash_password(PASSWORD),
        bio=None,
        avatar_id=None,
        created_at=datetime(2026, 11, 20, 14, tzinfo=UTC),
    )


@pytest.fixture
def auth_client(session, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", KEY)
    monkeypatch.setenv("JWT_EXPIRES_IN", "3600")
    app.dependency_overrides[get_session] = lambda: session
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def bearer(user_id):
    token = create_access_token(user_id).access_token
    return {"Authorization": f"Bearer {token}"}


def test_registration_normalizes_email_and_persists_only_hash(
    auth_client, session, user
):
    session.scalars.return_value.one_or_none.return_value = user
    body = {
        "display_name": "  Pessoa cinéfila  ",
        "email": "CINEFILA@Example.com",
        "password": PASSWORD,
    }

    response = auth_client.post(REGISTER, json=body)

    assert response.status_code == 201
    assert response.json() == {
        "user_id": str(user.id),
        "display_name": user.display_name,
        "created_at": "2026-11-20T14:00:00Z",
    }
    statement = session.scalars.call_args.args[0]
    values = statement.compile().params
    assert values["email"] == user.email
    assert values["display_name"] == user.display_name
    assert values["password_hash"].startswith("$argon2id$")
    assert verify_password(values["password_hash"], PASSWORD)
    assert PASSWORD not in str(values)
    session.commit.assert_called_once()

    session.scalars.return_value.one_or_none.return_value = None
    response = auth_client.post(REGISTER, json=body)
    assert (
        response.status_code == 409 and response.json()["error"]["code"] == "CONFLICT"
    )
    session.commit.assert_called_once()


def test_login_session_and_public_profile_hide_credentials(auth_client, session, user):
    session.scalar.return_value = user
    session.get.return_value = user
    login = auth_client.post(LOGIN, json={"email": user.email, "password": PASSWORD})

    assert login.status_code == 200
    assert login.json()["expires_in"] == 3600
    assert login.json()["token_type"] == "bearer"
    token = login.json()["access_token"]
    claims = jwt.decode(token, KEY, algorithms=["HS256"])
    assert claims["sub"] == str(user.id)
    session_response = auth_client.get(ME, headers={"Authorization": f"Bearer {token}"})
    assert session_response.status_code == 200
    assert session_response.json() == {
        "user_id": str(user.id),
        "display_name": user.display_name,
        "email": user.email,
        "created_at": "2026-11-20T14:00:00Z",
        "bio": None,
        "avatar_id": None,
        "avatar_image_url": None,
        "background_image_url": None,
    }
    profile = auth_client.get(f"{USERS}/{user.id}")
    assert profile.status_code == 200
    assert profile.json() == {
        "user_id": str(user.id),
        "display_name": user.display_name,
        "created_at": "2026-11-20T14:00:00Z",
        "bio": None,
        "avatar_id": None,
        "avatar_image_url": None,
        "background_image_url": None,
        "archetype": None,
    }

    wrong = auth_client.post(LOGIN, json={"email": user.email, "password": "errada"})
    session.scalar.return_value = None
    absent = auth_client.post(LOGIN, json={"email": user.email, "password": "errada"})
    assert wrong.status_code == absent.status_code == 401
    assert wrong.json() == absent.json()


def test_patch_targets_token_account_and_validates_fields(auth_client, session, user):
    headers = bearer(user.id)
    session.get.return_value = user
    session.scalars.return_value.one_or_none.return_value = user

    response = auth_client.patch(
        f"{USERS}/me", headers=headers, json={"bio": None, "avatar_id": "avatar-08"}
    )

    assert response.status_code == 200
    statement = session.scalars.call_args.args[0]
    assert statement.compile().params == {
        "bio": None,
        "avatar_id": "avatar-08",
        "id_1": user.id,
    }
    session.commit.assert_called_once()
    assert auth_client.patch(f"{USERS}/me", json={}).status_code == 401
    assert auth_client.patch(f"{USERS}/me", headers=headers, json={}).status_code == 200
    for body in (
        {"bio": "a" * 161},
        {"avatar_id": "https://example.com/avatar.png"},
        {"user_id": str(uuid4())},
    ):
        assert (
            auth_client.patch(f"{USERS}/me", headers=headers, json=body).status_code
            == 422
        )
    session.commit.assert_called_once()
    avatars = auth_client.get("/api/v1/avatars")
    assert avatars.json()["items"] == [{"id": f"avatar-{i:02}"} for i in range(1, 9)]


def test_history_uses_user_filter_newest_sort_counts_and_pagination(
    auth_client, session, user, review
):
    session.get.return_value = user
    session.execute.return_value = [(review, 2, 3, 4)]
    session.scalar.return_value = 5
    route = f"{USERS}/{user.id}/reviews"

    response = auth_client.get(route, params={"page": 2, "page_size": 1})

    assert response.status_code == 200
    result = response.json()
    assert (result["total"], result["page"], result["page_size"]) == (5, 2, 1)
    assert result["items"][0]["movie_id"] == review.movie_id
    assert result["items"][0]["counts"] == {"like": 2, "spoiler": 3, "well_argued": 4}
    query = str(session.execute.call_args.args[0])
    assert "WHERE reviews.user_id = " in query
    assert "ORDER BY reviews.created_at DESC, reviews.id DESC" in query
    assert auth_client.get(route, params={"page_size": 51}).status_code == 422
    assert auth_client.get(route, params={"page": "invalid"}).status_code == 422
    session.get.return_value = None
    assert auth_client.get(route).status_code == 404


def test_token_failures_do_not_persist_reviews(
    auth_client, session, user, review_payload
):
    reviews = "/api/v1/reviews"
    expired = jwt.encode(
        {"sub": str(user.id), "exp": datetime.now(UTC) - timedelta(seconds=1)},
        KEY,
        algorithm="HS256",
    )
    for headers in (
        {},
        {"Authorization": ""},
        {"Authorization": "Basic abc"},
        {"Authorization": "Bearer malformed"},
        {"Authorization": f"Bearer {expired}"},
    ):
        response = auth_client.post(
            reviews,
            json={**review_payload, "author_name": "Visitante"},
            headers=headers,
        )
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "UNAUTHORIZED"
        assert response.headers["www-authenticate"] == "Bearer"
    session.add.assert_not_called()
    session.commit.assert_not_called()


@pytest.mark.parametrize(
    "legacy_fields", [{}, {"author_name": "Visitante"}, {"author_name": 1}]
)
def test_reviews_use_token_account_and_ignore_legacy_author_name(
    auth_client, session, user, review_payload, legacy_fields
):
    def assign_generated_fields(review):
        review.id = uuid4()
        review.created_at = user.created_at

    session.refresh.side_effect = assign_generated_fields
    session.get.return_value = user
    response = auth_client.post(
        "/api/v1/reviews",
        headers=bearer(user.id),
        json={**review_payload, **legacy_fields},
    )

    assert response.status_code == 201
    assert response.json()["author_name"] == user.display_name
    assert response.json()["author_id"] == str(user.id)
    session.get.assert_called_once_with(User, user.id)
    session.add.assert_called_once()
    saved = session.add.call_args.args[0]
    assert (saved.user_id, saved.author_name) == (user.id, user.display_name)
    session.commit.assert_called_once()


def test_movie_list_includes_legacy_anonymous_reviews(auth_client, session, review):
    assert review.user_id is None
    session.execute.return_value = [(review, 0, 0, 0)]
    session.scalar.return_value = 1

    response = auth_client.get(f"/api/v1/movies/{review.movie_id}/reviews")

    assert response.status_code == 200
    assert response.json()["total"] == 1
    (item,) = response.json()["items"]
    assert (item["id"], item["author_name"]) == (str(review.id), review.author_name)
    assert item["author_id"] is None
    statement = session.execute.call_args.args[0]
    assert statement.whereclause.compare(Review.movie_id == review.movie_id)


def test_invalid_jwt_configuration_and_cors(auth_client, session, user, monkeypatch):
    session.scalar.return_value = user
    monkeypatch.setenv("JWT_EXPIRES_IN", "0")
    login = auth_client.post(LOGIN, json={"email": user.email, "password": PASSWORD})
    assert login.status_code == 503
    response = auth_client.options(
        f"{USERS}/me",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "authorization, content-type",
        },
    )
    assert response.status_code == 200
    assert "Authorization" in response.headers["access-control-allow-headers"]
    assert "PATCH" in response.headers["access-control-allow-methods"]


def test_openapi_requires_bearer_for_review_and_profile_edits(
    auth_client,
):
    schema = auth_client.get("/api/openapi.json").json()
    paths = schema["paths"]
    publication = paths["/api/v1/reviews"]["post"]
    assert publication["security"] == [{"HTTPBearer": []}]
    assert "401" in publication["responses"]
    request_schema = schema["components"]["schemas"]["ReviewSubmission"]
    assert "author_name" not in request_schema["properties"]
    assert paths["/api/v1/users/me"]["patch"]["security"] == [{"HTTPBearer": []}]


def image_bytes(fmt="PNG", size=(64, 32), **kwargs):
    with Image.new("RGB", size, "red") as image, BytesIO() as output:
        image.save(output, fmt, **kwargs)
        return output.getvalue()


@pytest.mark.parametrize(
    ("kind", "size", "output_size"),
    [("avatar", (800, 400), (512, 256)), ("background", (2400, 1200), (1920, 960))],
)
def test_profile_image_upload_normalizes_and_exposes_url(
    auth_client, session, user, kind, size, output_size
):
    session.get.return_value = user
    metadata = PngInfo()
    metadata.add_text("Description", "Metadado original")

    result = auth_client.put(
        f"{USERS}/me/images/{kind}",
        headers={**bearer(user.id), "Content-Type": "image/png"},
        content=image_bytes(size=size, pnginfo=metadata),
    )

    assert result.status_code == 200
    url = result.json()["url"]
    statement = session.execute.call_args.args[0]
    assert "ON CONFLICT (user_id, kind) DO UPDATE" in str(statement.compile())
    values = statement.compile().params
    assert values["kind"] == kind and values["user_id"] == user.id
    version = values["version"]
    assert url == f"{USERS}/{user.id}/images/{kind}/{version}"
    with Image.open(BytesIO(values["content"])) as image:
        assert image.format == "WEBP" and image.size == output_size
        assert "exif" not in image.info and "Description" not in image.info

    picture = ProfileImage(
        user_id=user.id, kind=kind, version=version, content=values["content"]
    )
    user.profile_images = [picture]
    session.scalar.return_value = picture
    profile = auth_client.get(f"{USERS}/{user.id}").json()
    assert profile[f"{kind}_image_url"] == url
    assert (
        auth_client.get(ME, headers=bearer(user.id)).json()[f"{kind}_image_url"] == url
    )

    response = auth_client.get(url)
    assert response.status_code == 200 and response.content == picture.content
    assert response.headers["content-type"] == "image/webp"
    assert response.headers["cache-control"] == "no-store"

    session.scalar.return_value = None
    assert auth_client.get(url).status_code == 404


def test_exif_orientation_is_applied_before_removing_metadata(
    auth_client, session, user
):
    session.get.return_value = user
    exif = Image.Exif()
    exif[274] = 6
    result = auth_client.put(
        f"{USERS}/me/images/avatar",
        headers={**bearer(user.id), "Content-Type": "image/jpeg"},
        content=image_bytes("JPEG", exif=exif),
    )
    assert result.status_code == 200
    saved = session.execute.call_args.args[0].compile().params["content"]
    with Image.open(BytesIO(saved)) as image:
        assert image.size == (32, 64)
        assert not image.getexif()


def test_rejected_images_do_not_change_database(
    auth_client, session, user, monkeypatch
):
    session.get.return_value = user
    route = f"{USERS}/me/images/avatar"
    key = bearer(user.id)
    with Image.new("RGB", (16, 16), "blue") as animated_frame, BytesIO() as animation:
        payloads = [
            (image_bytes(), "image/svg+xml", 415, "UNSUPPORTED_MEDIA_TYPE"),
            (image_bytes(), "image/jpeg", 415, "UNSUPPORTED_MEDIA_TYPE"),
            (b"not an image", "image/png", 422, "VALIDATION_ERROR"),
            (image_bytes(size=(4097, 1)), "image/png", 413, "PAYLOAD_TOO_LARGE"),
        ]
        with Image.new("RGB", (16, 16), "red") as first_frame:
            first_frame.save(
                animation, "PNG", save_all=True, append_images=[animated_frame]
            )
        payloads.append((animation.getvalue(), "image/png", 422, "VALIDATION_ERROR"))
        for payload, media_type, code, error_code in payloads:
            response = auth_client.put(
                route, content=payload, headers={**key, "Content-Type": media_type}
            )
            assert response.status_code == code
            assert response.json()["error"]["code"] == error_code

    monkeypatch.setattr("controllers.users.MAX_IMAGE_BYTES", 10)
    response = auth_client.put(
        route,
        content=iter([b"123456", b"6789a"]),
        headers={**key, "Content-Type": "image/png"},
    )
    assert response.status_code == 413
    session.execute.assert_not_called()
    session.commit.assert_not_called()


def test_only_token_account_can_upload_or_delete_images(auth_client, session, user):
    route = f"{USERS}/me/images/background"
    assert auth_client.put(route).status_code == 401
    assert auth_client.delete(route).status_code == 401

    key = bearer(user.id)
    session.get.return_value = None
    assert auth_client.delete(route, headers=key).status_code == 401
    session.execute.assert_not_called()

    session.get.return_value = user
    for _attempt in range(2):
        response = auth_client.delete(route, headers=key)
        assert response.status_code == 204 and response.content == b""
    params = session.execute.call_args.args[0].compile().params
    assert params == {"user_id_1": user.id, "kind_1": "background"}


def test_image_upload_and_delete_cors_and_openapi(auth_client):
    route = f"{USERS}/me/images/background"
    for method in ("PUT", "DELETE"):
        response = auth_client.options(
            route,
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": method,
                "Access-Control-Request-Headers": "authorization, content-type",
            },
        )
        assert response.status_code == 200
        assert method in response.headers["access-control-allow-methods"]
    paths = auth_client.get("/api/openapi.json").json()["paths"]
    upload = paths[f"{USERS}/me/images/{{kind}}"]["put"]
    assert set(upload["requestBody"]["content"]) == {
        "image/jpeg",
        "image/png",
        "image/webp",
    }
    assert upload["security"] == [{"HTTPBearer": []}]
    image = paths[f"{USERS}/{{user_id}}/images/{{kind}}/{{version}}"]["get"]
    assert set(image["responses"]["200"]["content"]) == {"image/webp"}
