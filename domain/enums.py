from enum import StrEnum


class InteractionType(StrEnum):
    VIEW = "view"
    LIKE = "like"
    WATCHLIST = "watchlist"
    WATCHED = "watched"
