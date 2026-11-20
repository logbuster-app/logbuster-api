import pytest

from services.archetype import MIN_REVIEWS, ReviewFacts, classify


def facts(*ratings, **extra):
    return [ReviewFacts(rating=rating, **extra) for rating in ratings]


def test_below_minimum_has_no_archetype():
    assert classify([]) is None
    assert classify(facts(5.0, 5.0)) is None
    assert MIN_REVIEWS == 3


def test_third_review_unlocks_archetype_and_changes_follow_the_data():
    reviews = facts(5.0, 4.5)
    assert classify(reviews) is None

    reviews.append(ReviewFacts(rating=5.0))
    assert classify(reviews).title == "Coração mole"

    # Recalculado a partir dos dados: notas baixas mudam o resultado.
    reviews.extend(facts(1.0, 0.5, 1.0, 0.5))
    assert classify(reviews).title == "Crítico exigente"


@pytest.mark.parametrize(
    ("reviews", "title", "fragment"),
    [
        (facts(3.0, 3.5, 3.0, well_argued_votes=2), "Voz da comunidade", "2,0 votos"),
        (
            [
                ReviewFacts(3.0, is_spoiler=True),
                ReviewFacts(3.5, spoiler_votes=3),
                ReviewFacts(3.0),
            ],
            "Contador de finais",
            "67%",
        ),
        (facts(1.0, 2.5, 2.0), "Crítico exigente", "Média de 1,8 estrelas"),
        (facts(4.5, 4.0, 5.0), "Coração mole", "Média de 4,5 estrelas"),
        (
            facts(3.0, 3.5, 3.0, highlights=("acting",)),
            "Fã de atuações",
            "Destaca as atuações em 100%",
        ),
        (facts(3.0, 3.5, 4.0), "Equilibrado", "Média de 3,5 estrelas"),
    ],
)
def test_each_archetype_explains_the_classification(reviews, title, fragment):
    result = classify(reviews)
    assert result.title == title
    assert fragment in result.description


def test_precedence_prefers_community_votes_over_spoilers_and_ratings():
    reviews = facts(1.0, 1.0, 1.0, is_spoiler=True, well_argued_votes=5)
    assert classify(reviews).title == "Voz da comunidade"

    reviews = facts(5.0, 5.0, 5.0, is_spoiler=True)
    assert classify(reviews).title == "Contador de finais"


def test_two_community_spoiler_votes_do_not_count_as_spoiler():
    reviews = facts(3.0, 3.5, 3.0, spoiler_votes=2)
    assert classify(reviews).title == "Equilibrado"


def test_specialist_ignores_unknown_highlights_and_breaks_ties_by_enum_order():
    reviews = [
        ReviewFacts(3.0, highlights=("direction", "invalido")),
        ReviewFacts(3.5, highlights=("soundtrack",)),
        ReviewFacts(3.0, highlights=("direction", "soundtrack")),
    ]
    # Empate 2 x 2: soundtrack vem antes de direction no enum.
    assert classify(reviews).title == "Ouvido de trilha"


def test_specialist_needs_highlight_in_at_least_half_of_reviews():
    reviews = [
        ReviewFacts(3.0, highlights=("screenplay",)),
        ReviewFacts(3.5),
        ReviewFacts(3.0),
    ]
    assert classify(reviews).title == "Equilibrado"
