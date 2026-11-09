from enum import StrEnum


class Highlight(StrEnum):
    """Pontos de destaque de uma avaliação (SPEC-API-00, RN-04)."""

    SOUNDTRACK = "soundtrack"
    CINEMATOGRAPHY = "cinematography"
    SCREENPLAY = "screenplay"
    ACTING = "acting"
    DIRECTION = "direction"
    VISUAL_EFFECTS = "visual_effects"


class ReviewInteractionType(StrEnum):
    """Reações de leitores sobre uma avaliação (SPEC-API-00, RN-04)."""

    LIKE = "like"
    SPOILER = "spoiler"
    WELL_ARGUED = "well_argued"


class ReviewSort(StrEnum):
    """Ordenações da lista de avaliações de um filme (SPEC-BACK-02, RN-01)."""

    WELL_ARGUED = "well_argued"
    MOST_LIKED = "most_liked"
    NEWEST = "newest"
    RATING_DESC = "rating_desc"
    RATING_ASC = "rating_asc"
