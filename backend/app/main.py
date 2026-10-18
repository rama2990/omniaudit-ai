from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import select

from app.api import router
from app.db import ROOT, init_db, session
from app.models import Spv

DIST = ROOT.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_app):
    init_db()
    with session() as s:
        empty = s.exec(select(Spv)).first() is None
    if empty:  # start pertama: isi data seed otomatis
        from app.seed import seed
        seed()
    yield


app = FastAPI(title="OmniAudit AI", lifespan=lifespan)
app.include_router(router)

if DIST.exists():  # satu proses menyajikan frontend (siap Cloud Run)
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = DIST / path
        return FileResponse(f if path and f.is_file() else DIST / "index.html")
