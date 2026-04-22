from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routes.home import router as home_router


app = FastAPI(title="File Conversion App")

# Optional static files (CSS, JS, images)
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(home_router)
