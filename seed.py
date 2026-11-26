"""Popula o banco SQLite com um grande volume de dados realistas de demonstração.

Uso:
    python seed.py
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from domain.enums import Highlight, ReviewInteractionType
from domain.models.review import Review
from domain.models.review_interaction import ReviewInteraction
from domain.models.review_summary import ReviewSummary
from domain.models.user import User
from utils.database import create_session
from utils.security import hash_password

FAKE_USERS = [
    ("Ana Clara", "ana@logbuster.dev", "Fã de ficção científica, thrillers psicológicos e trilhas sonoras marcantes."),
    ("Carlos Eduardo", "carlos@logbuster.dev", "Crítico amador de fim de semana. Sempre reparo na fotografia."),
    ("Marina Silva", "marina@logbuster.dev", "Maratonando clássicos e cinema sul-coreano."),
    ("Lucas Ferreira", "lucas@logbuster.dev", "Se tem direção de Nolan ou Villeneuve, eu assisto na estreia."),
    ("Sofia Mendes", "sofia@logbuster.dev", "Apreciadora de bons roteiros, diálogos afiados e atuações intensas."),
    ("Rafael Costa", "rafael@logbuster.dev", "Cinéfilo de carteirinha. Colecionador de trilhas sonoras em vinil."),
    ("Juliana Rocha", "juliana@logbuster.dev", "Amo animações, dramas históricos e filmes com final aberto."),
    ("Pedro Henrique", "pedro@logbuster.dev", "Viciado em ação prática, montagem rápida e cinema dos anos 90."),
    ("Beatriz Almeida", "beatriz@logbuster.dev", "Observo direção de arte e figurino antes de qualquer outra coisa."),
    ("Thiago Oliveira", "thiago@logbuster.dev", "Do terror indie aos blockbusters IMAX: assisto de tudo."),
    ("Camila Santos", "camila@logbuster.dev", "Cinema nacional e latino-americano no topo da minha lista."),
    ("Gabriel Lima", "gabriel@logbuster.dev", "Ficção especulativa, cyberpunk e distopias são minha praia."),
    ("Larissa Gomes", "larissa@logbuster.dev", "Buscando sempre histórias humanas bem contadas e sem pressa."),
    ("Matheus Ribeiro", "matheus@logbuster.dev", "Engenheiro de som nas horas vagas; julgo filmes pela mixagem."),
    ("Fernanda Barbosa", "fernanda@logbuster.dev", "Amante de mistérios, noir e reviravoltas bem construídas."),
    ("Bruno Carvalho", "bruno@logbuster.dev", "Fã de épicos de fantasia e sagas que respeitam o público."),
    ("Isabela Martins", "isabela@logbuster.dev", "Sempre avaliando ritmo, atuação de elenco e peso emocional."),
    ("Diego Nogueira", "diego@logbuster.dev", "Reassistindo clássicos para ver quais realmente resistem ao tempo."),
    ("Patrícia Azevedo", "patricia@logbuster.dev", "Dramas de tribunal, biografias e roteiros baseados em fatos."),
    ("Vinícius Teixeira", "vinicius@logbuster.dev", "Se o filme me fizer pensar por uma semana, já ganhou cinco estrelas."),
]

# Filmes reais no IMDb / OMDb: (movie_id, título para resumo, resumo pré-gerado opcional)
MOVIES: list[tuple[str, str, str | None]] = [
    ("tt0133093", "The Matrix", "A comunidade destaca The Matrix como um marco técnico e narrativo: efeitos visuais revolucionários, direção precisa e trilha sonora icônica sustentam um roteiro filosófico que continua atual."),
    ("tt1375666", "Inception", "O público elogia a ambição de Christopher Nolan ao combinar filme de assalto e ficção científica, ressaltando a montagem frenética, a trilha de Hans Zimmer e o peso emocional do protagonista."),
    ("tt0816692", "Interstellar", "As avaliações celebram a escala visual, a trilha sonora arrebatadora e a carga emocional da relação entre pai e filha, apontando o filme como uma experiência sensorial marcante."),
    ("tt0468569", "The Dark Knight", "Consenso absoluto em torno da atuação histórica de Heath Ledger, da fotografia em IMAX e da abordagem realista e tensa de drama policial."),
    ("tt6751668", "Parasite", "Elogiado pela precisão cirúrgica do roteiro e da direção de Bong Joon-ho, que transita entre humor ácido, crítica social e suspense sem perder o controle do tom."),
    ("tt15398776", "Oppenheimer", "A comunidade destaca a atuação magnética de Cillian Murphy, o ritmo acelerado da montagem e o uso impressionante do som para sustentar três horas de tensão psicológica."),
    ("tt0111161", "The Shawshank Redemption", "Considerado atemporal pelos leitores, com destaque para a química do elenco, a narração envolvente e um roteiro sobre esperança que emociona mesmo em revisitas."),
    ("tt0110912", "Pulp Fiction", "Os espectadores apontam os diálogos inesquecíveis, a estrutura não linear e a trilha sonora estilosa como os grandes motores deste clássico dos anos 90."),
    ("tt0137523", "Fight Club", None),
    ("tt0109830", "Forrest Gump", None),
    ("tt0068646", "The Godfather", "Aclamação unânime pela direção clássica, atuações lendárias e construção de personagem, citado repetidamente como referência máxima em roteiro dramático."),
    ("tt0120737", "The Lord of the Rings: The Fellowship of the Ring", None),
    ("tt0167260", "The Lord of the Rings: The Return of the King", None),
    ("tt1160419", "Dune", None),
    ("tt15239678", "Dune: Part Two", "A comunidade exalta a grandiosidade visual, o design de som avassalador e a evolução sombria do protagonista sob a direção segura de Denis Villeneuve."),
    ("tt9362722", "Spider-Man: Across the Spider-Verse", None),
    ("tt6710474", "Everything Everywhere All at Once", None),
    ("tt2582802", "Whiplash", "Avaliações ressaltam a intensidade sufocante da montagem, o duelo psicológico entre os protagonistas e a energia elétrica das sequências musicais."),
    ("tt0245429", "Spirited Away", None),
    ("tt0317248", "City of God", "Destaque absoluto para a montagem ágil, a força visceral da fotografia e as atuações naturais que retratam a realidade com impacto duradouro."),
    ("tt0099685", "Goodfellas", None),
    ("tt0114369", "Se7en", None),
    ("tt0102926", "The Silence of the Lambs", None),
    ("tt7286456", "Joker", None),
    ("tt1856101", "Blade Runner 2049", None),
]

HIGHLIGHT_PAIRS = [
    [Highlight.DIRECTION.value, Highlight.CINEMATOGRAPHY.value],
    [Highlight.SCREENPLAY.value, Highlight.ACTING.value],
    [Highlight.SOUNDTRACK.value, Highlight.VISUAL_EFFECTS.value],
    [Highlight.ACTING.value, Highlight.DIRECTION.value],
    [Highlight.CINEMATOGRAPHY.value, Highlight.SOUNDTRACK.value],
    [Highlight.SCREENPLAY.value, Highlight.DIRECTION.value],
    [Highlight.VISUAL_EFFECTS.value, Highlight.DIRECTION.value],
    [Highlight.ACTING.value],
    [Highlight.SCREENPLAY.value],
]

RATINGS = [
    Decimal("5.0"),
    Decimal("4.5"),
    Decimal("5.0"),
    Decimal("4.0"),
    Decimal("4.5"),
    Decimal("3.5"),
    Decimal("5.0"),
    Decimal("4.0"),
]

REVIEW_TEMPLATES = [
    "Obra impressionante do começo ao fim. A direção segura transforma cada cena em um momento memorável, sem deixar o ritmo cair em nenhum instante.",
    "Roteiro muito bem amarrado, com personagens que têm motivações claras e diálogos que realmente dizem algo. Vale cada minuto.",
    "A fotografia e o desenho de som criam uma atmosfera hipnotizante. É o tipo de filme que melhora ainda mais quando assistido com atenção total.",
    "Atuações de altíssimo nível sustentam toda a carga dramática da história. Mesmo nos momentos mais silenciosos, a tensão é palpável.",
    "Visualmente grandioso e com uma trilha sonora que dita o pulso emocional da narrativa. Saí da sessão pensando nas escolhas do terceiro ato.",
    "Tem alguns trechos um pouco mais lentos no meio, mas a recompensa no clímax compensa demais. Construção de mundo impecável.",
    "Reassisti depois de anos e continua incrivelmente atual. A montagem ágil e o cuidado técnico colocam este filme muito acima da média.",
    "Não esperava me envolver tanto com os conflitos secundários, mas o texto acerta em cheio ao equilibrar espetáculo e humanidade.",
]

SPOILER_TEMPLATES = [
    "A reviravolta nos minutos finais muda completamente a leitura de todas as cenas anteriores; o plano detalhe na última tomada entrega tudo.",
    "Quando o personagem principal percebe que toda a investigação foi manipulada desde o início, a tensão atinge o ápice antes do desfecho trágico.",
]


def main() -> None:
    session = create_session()
    try:
        password_hash = hash_password("logbuster123")
        users: list[User] = []

        for display_name, email, bio in FAKE_USERS:
            user = session.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(
                    id=uuid4(),
                    display_name=display_name,
                    email=email,
                    password_hash=password_hash,
                    bio=bio,
                )
                session.add(user)
                session.flush()
            users.append(user)

        existing_pairs = set(
            session.execute(
                select(Review.movie_id, Review.user_id).where(Review.user_id.is_not(None))
            ).all()
        )

        now = datetime.now(UTC)
        new_reviews: list[Review] = []
        reviews_by_movie: dict[str, list[Review]] = {}

        # Carrega reviews existentes para compor summaries completos.
        for existing_review in session.scalars(select(Review)):
            reviews_by_movie.setdefault(existing_review.movie_id, []).append(existing_review)

        for m_idx, (movie_id, title, _summary) in enumerate(MOVIES):
            reviews_per_movie = 7 if m_idx < 10 else 6
            for r_idx in range(reviews_per_movie):
                author = users[(m_idx * 3 + r_idx) % len(users)]
                if (movie_id, author.id) in existing_pairs:
                    continue

                is_spoiler = r_idx == reviews_per_movie - 1 and m_idx % 2 == 0
                if is_spoiler:
                    content = f"Sobre {title}: {SPOILER_TEMPLATES[(m_idx + r_idx) % len(SPOILER_TEMPLATES)]}"
                else:
                    content = f"Sobre {title}: {REVIEW_TEMPLATES[(m_idx + r_idx) % len(REVIEW_TEMPLATES)]}"

                review = Review(
                    id=uuid4(),
                    movie_id=movie_id,
                    author_name=author.display_name,
                    rating=RATINGS[(m_idx + r_idx) % len(RATINGS)],
                    content=content,
                    is_spoiler=is_spoiler,
                    highlights=HIGHLIGHT_PAIRS[(m_idx + r_idx) % len(HIGHLIGHT_PAIRS)],
                    created_at=now - timedelta(hours=(m_idx * 10 + r_idx * 3) + 1),
                    user_id=author.id,
                )
                session.add(review)
                new_reviews.append(review)
                reviews_by_movie.setdefault(movie_id, []).append(review)
                existing_pairs.add((movie_id, author.id))

        session.flush()

        # Gera interações variadas nas novas avaliações.
        interactions_added = 0
        for idx, review in enumerate(new_reviews):
            likes = (idx % 6) + 1
            well_argued = (idx % 4) + 1
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

        # Preenche resumos de IA em cache para os filmes principais.
        summaries_added = 0
        for movie_id, _title, summary_text in MOVIES:
            if summary_text is None:
                continue
            movie_reviews = reviews_by_movie.get(movie_id, [])
            eligible_ids: list[UUID] = [
                r.id for r in movie_reviews if not r.is_spoiler
            ][:10]
            if len(eligible_ids) < 3:
                continue
            stmt = insert(ReviewSummary).values(
                movie_id=movie_id,
                text=summary_text,
                generated_at=now,
                reviews_count=len(movie_reviews),
                source_review_ids=eligible_ids,
                failed_at=None,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[ReviewSummary.movie_id],
                set_={
                    "text": stmt.excluded.text,
                    "generated_at": stmt.excluded.generated_at,
                    "reviews_count": stmt.excluded.reviews_count,
                    "source_review_ids": stmt.excluded.source_review_ids,
                    "failed_at": None,
                },
            )
            session.execute(stmt)
            summaries_added += 1

        session.commit()
        print(
            f"Seed concluído: {len(users)} usuários, "
            f"{len(new_reviews)} novas avaliações ({len(MOVIES)} filmes), "
            f"{interactions_added} interações e {summaries_added} resumos de IA."
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
