from fastapi import FastAPI, BackgroundTasks, HTTPException, Security, Depends
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import os
from datetime import datetime
from dotenv import load_dotenv

# Load env
load_dotenv()

# Import existing logic
from main import WATCHLIST
from daily_swing_scan import get_swing_signals, send_telegram_report

# --- AUTH CONFIG ---
API_KEY = os.getenv("API_KEY")
API_KEY_NAME = "access_token" # Header name: 'access_token: mysecretkey'
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    if not API_KEY:
        # If no key set in env, allow access (Warning mode)
        print("⚠️ WARNING: No API_KEY set in .env! API is unsecured.")
        return api_key_header
        
    if api_key_header == API_KEY:
        return api_key_header
    else:
        raise HTTPException(
            status_code=403, 
            detail="Could not validate credentials"
        )

app = FastAPI(
    title="Swing Trading Screener API",
    description="API to control and view the Swing Trading Screener",
    version="1.0.0"
)

# In-memory storage for latest results (for simplicity)
latest_signals = {}
last_scan_time = None

class Signal(BaseModel):
    symbol: str
    strategy: str
    signal: str
    price: float
    stop_loss: float
    target: float
    confidence: float
    reason: str

class ScanResponse(BaseModel):
    status: str
    timestamp: str
    signals_found: int
    signals: List[Signal]

@app.get("/")
def health_check():
    return {
        "status": "online",
        "service": "Swing Trading Screener",
        "timestamp": datetime.now().isoformat(),
        "auth_enabled": bool(API_KEY)
    }

def run_scan_task(send_telegram: bool = True):
    global latest_signals, last_scan_time
    print(f"[{datetime.now()}] Starting background scan...")
    try:
        signals = get_swing_signals(WATCHLIST)
        
        # Store results
        latest_signals = signals
        last_scan_time = datetime.now()
        
        if send_telegram:
            send_telegram_report(signals)
            
        print(f"[{datetime.now()}] Scan complete. Found {len(signals)} signals.")
    except Exception as e:
        print(f"[{datetime.now()}] Scan Error: {e}")

@app.post("/scan", response_model=dict)
def trigger_scan(background_tasks: BackgroundTasks, send_telegram: bool = True, api_key: str = Depends(get_api_key)):
    """
    Trigger a manual scan in the background. Requires Auth.
    """
    background_tasks.add_task(run_scan_task, send_telegram)
    return {
        "message": "Scan started in background",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/results", response_model=ScanResponse)
def get_latest_results(api_key: str = Depends(get_api_key)):
    """
    Get the results of the last scan. Requires Auth.
    """
    if last_scan_time is None:
        raise HTTPException(status_code=404, detail="No scan has been run yet.")
        
    return {
        "status": "success",
        "timestamp": last_scan_time.isoformat(),
        "signals_found": len(latest_signals),
        "signals": latest_signals
    }

if __name__ == "__main__":
    # Allow running this file directly for development
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
