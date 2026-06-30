import os

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import settings
from routers import verify_api_key
from routers import projects, audit, findings
from db import startup_cleanup

APP_VERSION = "2026.06.30.2"

app = FastAPI(title="SecAudit API", version=APP_VERSION)


@app.on_event("startup")
def on_startup():
    startup_cleanup()


@app.middleware("http")
async def no_cache_assets(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    is_static_asset = path.startswith(("/static/", "/js/", "/css/")) and path.endswith((".js", ".css"))
    if is_static_asset:
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    return response


origins = [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_auth = [Depends(verify_api_key)]


@app.get("/api/version")
def api_version():
    return {"version": APP_VERSION}


app.include_router(projects.router, prefix="/api", dependencies=api_auth)
app.include_router(audit.router, prefix="/api", dependencies=api_auth)
app.include_router(findings.router, prefix="/api", dependencies=api_auth)

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    app.mount("/css", StaticFiles(directory=os.path.join(static_dir, "css")), name="css")
    app.mount("/js", StaticFiles(directory=os.path.join(static_dir, "js")), name="js")

    @app.get("/")
    def root():
        return FileResponse(os.path.join(static_dir, "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
