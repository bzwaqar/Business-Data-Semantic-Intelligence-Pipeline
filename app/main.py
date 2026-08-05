from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.api import router as api_router

app = FastAPI(title="CSV Classifier API")

app.include_router(api_router)

# Serve static frontend SPA with absolute path
static_dir = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

