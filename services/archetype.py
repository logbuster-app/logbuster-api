"""Arquétipo do cinéfilo, derivado das avaliações da conta (SPEC-BACK-09, RN-04).

Módulo puro e orientado por tabela: o catálogo, os limiares e a precedência
ficam nas constantes abaixo para a equipe ajustar sem mexer no restante. O
resultado nunca é guardado; é recalculado a cada consulta do perfil, então
qualquer mudança nos dados aparece no próximo cálculo.

Precedência (a primeira regra que casar vence):

1. Voz da comunidade — média de votos "bem argumentada" por avaliação alta.
2. Contador de finais — boa parte das avaliações com spoiler (do autor ou
   ocultada pela comunidade).
3. Crítico exigente — nota média baixa.
4. Coração mole — nota média alta.
5. Especialista — um destaque presente na maioria das avaliações.
6. Equilibrado — nenhum dos padrões acima.
"""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field

from domain.enums import Highlight
from domain.rules import SPOILER_VOTE_THRESHOLD

MIN_REVIEWS = 3

WELL_ARGUED_PER_REVIEW = 2.0
SPOILER_SHARE = 0.4
DEMANDING_AVERAGE = 2.5
SOFT_HEART_AVERAGE = 4.2
SPECIALIST_SHARE = 0.5

SPECIALISTS = {
    Highlight.SOUNDTRACK: ("Ouvido de trilha", "a trilha sonora"),
    Highlight.CINEMATOGRAPHY: ("Olhar de fotógrafo", "a fotografia"),
    Highlight.SCREENPLAY: ("Caçador de roteiros", "o roteiro"),
    Highlight.ACTING: ("Fã de atuações", "as atuações"),
    Highlight.DIRECTION: ("Cinéfilo de autor", "a direção"),
    Highlight.VISUAL_EFFECTS: ("Viciado em efeitos", "os efeitos visuais"),
}


@dataclass(frozen=True)
class ReviewFacts:
    rating: float
    is_spoiler: bool = False
    highlights: Sequence[str] = field(default_factory=tuple)
    spoiler_votes: int = 0
    well_argued_votes: int = 0


@dataclass(frozen=True)
class ArchetypeResult:
    title: str
    description: str


def _stars(value: float) -> str:
    return f"{value:.1f}".replace(".", ",")


def _percent(value: float) -> str:
    return f"{round(value * 100)}%"


def _top_highlight(reviews: Sequence[ReviewFacts]) -> tuple[Highlight, float] | None:
    counts: Counter[Highlight] = Counter()
    for review in reviews:
        for value in set(review.highlights):
            try:
                counts[Highlight(value)] += 1
            except ValueError:
                continue
    if not counts:
        return None
    # Empate: vale a ordem do enum, para o resultado não oscilar.
    order = list(Highlight)
    highlight = max(counts, key=lambda item: (counts[item], -order.index(item)))
    return highlight, counts[highlight] / len(reviews)


def classify(reviews: Sequence[ReviewFacts]) -> ArchetypeResult | None:
    """Arquétipo da conta, ou `None` abaixo de `MIN_REVIEWS` avaliações."""
    total = len(reviews)
    if total < MIN_REVIEWS:
        return None

    average = sum(review.rating for review in reviews) / total
    well_argued = sum(review.well_argued_votes for review in reviews) / total
    spoilers = sum(
        1
        for review in reviews
        if review.is_spoiler or review.spoiler_votes >= SPOILER_VOTE_THRESHOLD
    )
    spoiler_share = spoilers / total

    if well_argued >= WELL_ARGUED_PER_REVIEW:
        return ArchetypeResult(
            "Voz da comunidade",
            "Suas análises recebem em média "
            f"{_stars(well_argued)} votos de bem argumentada.",
        )
    if spoiler_share >= SPOILER_SHARE:
        return ArchetypeResult(
            "Contador de finais",
            f"{_percent(spoiler_share)} das suas avaliações têm spoiler: "
            "gosta de discutir o filme por inteiro.",
        )
    if average <= DEMANDING_AVERAGE:
        return ArchetypeResult(
            "Crítico exigente",
            f"Média de {_stars(average)} estrelas: reserva as notas altas "
            "para poucos filmes.",
        )
    if average >= SOFT_HEART_AVERAGE:
        return ArchetypeResult(
            "Coração mole",
            f"Média de {_stars(average)} estrelas: encontra algo para amar "
            "em quase todo filme.",
        )
    top = _top_highlight(reviews)
    if top is not None and top[1] >= SPECIALIST_SHARE:
        title, label = SPECIALISTS[top[0]]
        return ArchetypeResult(
            title, f"Destaca {label} em {_percent(top[1])} das suas avaliações."
        )
    return ArchetypeResult(
        "Equilibrado",
        f"Média de {_stars(average)} estrelas, sem extremos nem um aspecto favorito.",
    )
