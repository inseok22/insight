from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.admin.resource import router as admin_resource_router
from app.api.external.td import router as td_external_router
from app.api.router import api_router
from app.core.config import get_settings
from app.db.init_db import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    debug=settings.debug,
    lifespan=lifespan,
)

origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_v1_prefix)
app.include_router(admin_resource_router, prefix="/api")
app.include_router(td_external_router, prefix="/api")


@app.get("/", tags=["root"])
def read_root() -> dict[str, str]:
    return {"message": f"{settings.app_name} is running."}
