from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from molecula.api import health
from molecula.config import get_settings

app = FastAPI(title="Molecula")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router)
