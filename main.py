from contextlib import asynccontextmanager
from typing import AsyncGenerator

import pytz
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from tortoise.contrib.fastapi import RegisterTortoise

from app.orm_conn.tortoise_config import TORTOISE_ORM as tortoise_config
from app.routes import report

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # app startup
    async with RegisterTortoise(
            app,
            tortoise_config,
            generate_schemas=True,
            add_exception_handlers=True):
        yield


app = FastAPI(
    lifespan=lifespan,
    title="Fitness Studio Booking API",
    description="A comprehensive booking system for fitness classes",
    version="1.0.0"
)
allowed_origins = [
    "http://localhost",
    "http://localhost:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(report.router)