"""Popula o banco SQLite com usuários, avaliações e interações de demonstração.

Uso:
    python seed.py
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert

from domain.enums import Highlight, ReviewInteractionType
from domain.models.review import Review
from domain.models.review_interaction import ReviewInteraction
from domain.models.user import User
from utils.database import create_session
from utils.security import hash_password

FAKE_USERS = [
    {
        "display_name": "Ana Clara",
        "email": "ana@logbuster.dev",
        "bio": "Fã de ficção científica, thrillers psicológicos e trilhas sonoras marcantes.",
    },
    {
        "display_name": "Carlos Eduardo",
        "email": "carlos@logbuster.dev",
        "bio": "Crítico amador de fim de semana. Sempre reparo na fotografia.",
    },
    {
        "display_name": "Marina Silva",
        "email": "marina@logbuster.dev",
        "bio": "Maratonando clássicos e cinema sul-coreano.",
    },
    {
        "display_name": "Lucas Ferreira",
        "email": "lucas@logbuster.dev",
        "bio": "Se tem direção de Christopher Nolan ou Denis Villeneuve, eu assisto.",
    },
    {
        "display_name": "Sofia Mendes",
        "email": "sofia@logbuster.dev",
        "bio": "Apreciadora de bons roteiros e atuações intensas.",
    },
]

# (movie_id, user_index, rating, is_spoiler, highlights, content)
FAKE_REVIEWS = [
    (
        "tt0133093",
        0,
        Decimal("5.0"),
        False,
        [Highlight.VISUAL_EFFECTS.value, Highlight.DIRECTION.value],
        "Revolucionou o cinema de ação e ficção científica. A construção de mundo e as cenas em bullet time continuam impressionantes décadas depois.",
    ),
    (
        "tt0133093",
        1,
        Decimal("4.5"),
        False,
        [Highlight.SCREENPLAY.value, Highlight.SOUNDTRACK.value],
        "Roteiro inteligente que mistura filosofia com ação frenética sem perder o ritmo. A trilha sonora casa perfeitamente com cada cena.",
    ),
    (
        "tt0133093",
        2,
        Decimal("4.0"),
        True,
        [Highlight.ACTING.value],
        "A cena em que Neo acorda no mundo real e descobre que humanos são usados como baterias pela Matrix é um dos maiores choques do cinema.",
    ),
    (
        "tt0133093",
        3,
        Decimal("5.0"),
        False,
        [Highlight.CINEMATOGRAPHY.value, Highlight.VISUAL_EFFECTS.value],
        "Paleta esverdeada icônica dentro da simulação contrastando com os tons frios do mundo real. Obra-prima técnica.",
    ),
    (
        "tt1375666",
        3,
        Decimal("5.0"),
        False,
        [Highlight.DIRECTION.value, Highlight.SOUNDTRACK.value],
        "Nolan entrega um thriller de assalto dentro de sonhos com montagem impecável. A trilha do Hans Zimmer eleva a tensão do início ao fim.",
    ),
    (
        "tt1375666",
        4,
        Decimal("4.5"),
        False,
        [Highlight.SCREENPLAY.value, Highlight.ACTING.value],
        "Exige atenção em cada diálogo, mas recompensa muito. O conflito emocional do Cobb dá peso humano a toda a engenhosidade do roteiro.",
    ),
    (
        "tt1375666",
        1,
        Decimal("4.0"),
        True,
        [Highlight.CINEMATOGRAPHY.value],
        "A cena final com o pião girando antes do corte seco deixa exatamente a ambiguidade perfeita sobre se ele ainda está sonhando.",
    ),
    (
        "tt0816692",
        0,
        Decimal("5.0"),
        False,
        [Highlight.SOUNDTRACK.value, Highlight.VISUAL_EFFECTS.value],
        "Visualmente deslumbrante e emocionalmente devastador. A sequência no planeta de Miller e a música de órgão são inesquecíveis.",
    ),
    (
        "tt0816692",
        3,
        Decimal("4.5"),
        False,
        [Highlight.CINEMATOGRAPHY.value, Highlight.ACTING.value],
        "Matthew McConaughey entrega uma atuação emocionante como pai dividido entre salvar a humanidade e reencontrar a filha.",
    ),
    (
        "tt0468569",
        4,
        Decimal("5.0"),
        False,
        [Highlight.ACTING.value, Highlight.DIRECTION.value],
        "Heath Ledger como Coringa é uma das maiores atuações da história do cinema. Um filme de super-herói que funciona como drama policial sério.",
    ),
    (
        "tt0468569",
        1,
        Decimal("4.5"),
        False,
        [Highlight.CINEMATOGRAPHY.value, Highlight.SCREENPLAY.value],
        "Ritmo tenso do começo ao fim, sem gordura. A fotografia em IMAX dá uma escala grandiosa para Gotham.",
    ),
    (
        "tt6751668",
        2,
        Decimal("5.0"),
        False,
        [Highlight.SCREENPLAY.value, Highlight.DIRECTION.value],
        "Bong Joon-ho alterna humor ácido, tensão e crítica social com maestria absoluta. Cada enquadramento tem propósito.",
    ),
    (
        "tt6751668",
        4,
        Decimal("5.0"),
        False,
        [Highlight.ACTING.value, Highlight.CINEMATOGRAPHY.value],
        "Elenco inteiro em perfeita sintonia. A transição de tom na metade do filme é uma aula de direção.",
    ),
    (
        "tt15398776",
        3,
        Decimal("4.5"),
        False,
        [Highlight.ACTING.value, Highlight.SOUNDTRACK.value],
        "Cillian Murphy carrega o filme no olhar. Três horas que passam rápido graças à montagem frenética e ao som avassalador.",
    ),
    (
        "tt0111161",
        2,
        Decimal("5.0"),
        False,
        [Highlight.SCREENPLAY.value, Highlight.ACTING.value],
        "Uma história sobre esperança e amizade que nunca envelhece. Impossível não se emocionar no desfecho.",
    ),
    (
        "tt0110912",
        0,
        Decimal("4.5"),
        False,
        [Highlight.SCREENPLAY.value, Highlight.SOUNDTRACK.value],
        "Diálogos afiados, estrutura não linear brilhante e uma das trilhas sonoras mais estilosas já montadas.",
    ),
]


def main() -> None:
    session = create_session()
    try:
        password_hash = hash_password("logbuster123")
        users_by_email: dict[str, User] = {}

        for item in FAKE_USERS:
            existing = session.scalar(
                select(User).where(User.email == item["email"])
            )
            if existing is None:
                existing = User(
                    id=uuid4(),
                    display_name=item["display_name"],
                    email=item["email"],
                    password_hash=password_hash,
                    bio=item["bio"],
                )
                session.add(existing)
                session.flush()
            users_by_email[item["email"]] = existing

        existing_reviews = session.scalar(select(func.count(Review.id))) or 0
        if existing_reviews > 0:
            session.commit()
            print(
                f"Banco já possui {existing_reviews} avaliações; "
                f"usuários fake garantidos ({len(users_by_email)})."
            )
            return

        now = datetime.now(UTC)
        created_reviews: list[Review] = []
        for idx, (movie_id, user_idx, rating, is_spoiler, highlights, content) in enumerate(
            FAKE_REVIEWS
        ):
            author = users_by_email[FAKE_USERS[user_idx]["email"]]
            review = Review(
                id=uuid4(),
                movie_id=movie_id,
                author_name=author.display_name,
                rating=rating,
                content=content,
                is_spoiler=is_spoiler,
                highlights=highlights,
                created_at=now - timedelta(hours=(len(FAKE_REVIEWS) - idx) * 6),
                user_id=author.id,
            )
            session.add(review)
            created_reviews.append(review)

        session.flush()

        # Adiciona votos variados nas avaliações criadas.
        interactions_added = 0
        for idx, review in enumerate(created_reviews):
            likes = (idx % 4) + 1
            well_argued = (idx % 3) + 1
            for v in range(likes):
                session.execute(
                    insert(ReviewInteraction)
                    .values(
                        id=uuid4(),
                        review_id=review.id,
                        visitor_id=f"seed-like-{v}",
                        type=ReviewInteractionType.LIKE,
                    )
                    .on_conflict_do_nothing(
                        index_elements=[
                            ReviewInteraction.review_id,
                            ReviewInteraction.visitor_id,
                            ReviewInteraction.type,
                        ]
                    )
                )
                interactions_added += 1
            for v in range(well_argued):
                session.execute(
                    insert(ReviewInteraction)
                    .values(
                        id=uuid4(),
                        review_id=review.id,
                        visitor_id=f"seed-arg-{v}",
                        type=ReviewInteractionType.WELL_ARGUED,
                    )
                    .on_conflict_do_nothing(
                        index_elements=[
                            ReviewInteraction.review_id,
                            ReviewInteraction.visitor_id,
                            ReviewInteraction.type,
                        ]
                    )
                )
                interactions_added += 1

        session.commit()
        print(
            f"Seed concluído: {len(users_by_email)} usuários, "
            f"{len(created_reviews)} avaliações e {interactions_added} interações."
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
