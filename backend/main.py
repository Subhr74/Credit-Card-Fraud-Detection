"""Main FastAPI application entry point for SentinelDW Fraud Analytics Website."""
import os
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.config import BASE_DIR
from backend.database import init_db, execute_query
from backend.simulator import simulator
from backend.ml_service import get_bundle

# Routers
from backend.routes.kpis import router as kpis_router
from backend.routes.olap import router as olap_router
from backend.routes.etl_runs import router as etl_router
from backend.routes.models import router as models_router
from backend.routes.predict import router as predict_router
from backend.routes.review import router as review_router
from backend.routes.stream import router as stream_router
from backend.routes.warehouse import router as warehouse_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    try:
        get_bundle()
    except Exception as e:
        print(f"[BACKEND WARNING] Model not preloaded: {e}")
    yield
    simulator.stop()

app = FastAPI(
    title="SentinelDW Fraud Analytics Portal",
    description="Enterprise Credit Card Fraud Analytics & Data Warehouse Website",
    version="2.1.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(kpis_router)
app.include_router(olap_router)
app.include_router(etl_router)
app.include_router(models_router)
app.include_router(predict_router)
app.include_router(review_router)
app.include_router(stream_router)
app.include_router(warehouse_router)

@app.get("/api/health", tags=["Health"])
def health_check():
    db_ok = False
    try:
        res = execute_query("SELECT COUNT(*) as count FROM dim_time")
        db_ok = len(res) > 0
    except Exception:
        db_ok = False

    model_name = "None"
    try:
        bundle = get_bundle()
        model_name = bundle.get("name", "Unknown")
    except Exception:
        pass

    return {
        "status": "HEALTHY" if db_ok else "DEGRADED",
        "database_connected": db_ok,
        "deployed_model": model_name,
        "simulator_active": simulator.is_running,
    }

# Mount static frontend directory
frontend_dir = BASE_DIR / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

    @app.get("/", include_in_schema=False)
    @app.get("/index.html", include_in_schema=False)
    def serve_frontend():
        return FileResponse(frontend_dir / "index.html")

    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=False)
