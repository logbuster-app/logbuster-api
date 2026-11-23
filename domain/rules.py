"""Regras de negócio compartilhadas entre serviços e repositórios."""

# Votos de spoiler da comunidade que ocultam uma avaliação (CR-02, RN-04).
# Era 3 na SPEC-BACK-06; passou a 10 para cobrir filmes que a IA não conhece
# sem facilitar que um grupo pequeno esconda avaliações boas. O front usa o
# mesmo valor. Também tira a avaliação do resumo por IA e conta como uso de
# spoiler no arquétipo.
SPOILER_VOTE_THRESHOLD = 10
