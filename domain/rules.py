"""Regras de negócio compartilhadas entre serviços e repositórios."""

# Votos de spoiler da comunidade que ocultam uma avaliação (SPEC-BACK-06).
# A SPEC-BACK-09 também usa esse limite para tirar a avaliação do resumo por
# IA e para contar uso de spoiler no arquétipo.
SPOILER_HIDE_VOTES = 3
