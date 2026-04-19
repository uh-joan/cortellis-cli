import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from web.server import db
from web.server.routes import conversations, wiki, memory, internal


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-import CLI session history on startup
    try:
        from web.server.history import import_cli_history
        created = import_cli_history(_WORKSPACE)
        if created:
            print(f"  Imported {created} CLI session(s) into conversation history.")
    except Exception:
        pass
    yield


app = FastAPI(title="Cortellis Web", docs_url="/api/docs", redoc_url=None, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:7337", "http://127.0.0.1:7337"],
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(conversations.router, prefix="/api")
app.include_router(wiki.router, prefix="/api")
app.include_router(memory.router, prefix="/api")
app.include_router(internal.router, prefix="/api")

# Workspace is always the repo root (two levels up from web/server/)
_WORKSPACE = str(Path(__file__).resolve().parents[2])

@app.get("/api/config")
def get_config():
    return {"workspace_path": _WORKSPACE}

db.init_db()

# Serve the built React app — populated by `npm run build` inside web/ui/
_static = Path(__file__).parent.parent / "ui" / "dist"
if _static.exists():
    app.mount("/", StaticFiles(directory=str(_static), html=True), name="static")
