from fastapi import FastAPI

from backend.hardship.api import router as hardship_router

app = FastAPI(title="Heirloom API")
app.include_router(hardship_router)
