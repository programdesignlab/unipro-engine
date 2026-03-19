from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from momentum_edge.config import settings

engine = create_engine(settings.database_url, echo=settings.app_env == "development")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """Dependency-injectable DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
