from fastapi import FastAPI

from molecula.api import health

app = FastAPI(title="Molecula")
app.include_router(health.router)
