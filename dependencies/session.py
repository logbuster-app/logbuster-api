from collections.abc import Generator

from sqlalchemy.orm import Session

from utils.database import create_session


def get_session() -> Generator[Session, None, None]:
    session = create_session()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
