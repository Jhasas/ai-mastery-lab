from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config.database import init_db
from app.exceptions.handlers import register_exception_handlers
from app.routers.account_router import router as account_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="AI Mastery Lab", version="0.1.0", lifespan=lifespan)

register_exception_handlers(app)
app.include_router(account_router)
