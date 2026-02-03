from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import logger, API_KEY
from app.api.routers import scan, portfolio
from app.db.database import init_db
from datetime import datetime
import uvicorn

app = FastAPI(
    title="Swing Trading Screener API",
    description="Production-Ready API for Trading Automation",
    version="1.1.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup Event
@app.on_event("startup")
async def startup_event():
    logger.info("Starting up...")
    # Initialize DB (creates tables if not exist)
    init_db()

@app.get("/")
def health_check():
    return {
        "status": "online",
        "service": "Swing Trading Screener",
        "timestamp": datetime.now().isoformat(),
        "auth_enabled": bool(API_KEY)
    }

# Include Routers
app.include_router(scan.router, tags=["Scanner"])
app.include_router(portfolio.router, tags=["Portfolio"])

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
