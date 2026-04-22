from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routes.home import router as home_router


app = FastAPI(title="File Conversion App")

# Optional static files (CSS, JS, images)
app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(home_router)
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import os

app = FastAPI()

# make sure folders exist (important for Render)
os.makedirs("uploads", exist_ok=True)
os.makedirs("outputs", exist_ok=True)

# templates
templates = Jinja2Templates(directory="templates")

# ✅ FIX: homepage route
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})