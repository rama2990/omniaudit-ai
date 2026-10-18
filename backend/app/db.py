import os
from pathlib import Path

from dotenv import load_dotenv
from sqlmodel import Session, SQLModel, create_engine

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
DATA = Path(os.getenv("OMNI_DATA", ROOT / "data"))
DATA.mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{DATA / 'omniaudit.db'}", connect_args={"check_same_thread": False})


def init_db(reset: bool = False):
    from app import models  # noqa: F401 - register tables
    if reset:
        SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)


def session() -> Session:
    return Session(engine, expire_on_commit=False)
