from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import os
from datetime import datetime

# Import existing logic
from main import WATCHLIST
from daily_swing_scan import get_swing_signals, send_telegram_report

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
        "timestamp": datetime.now().isoformat()
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
def trigger_scan(background_tasks: BackgroundTasks, send_telegram: bool = True):
    """
    Trigger a manual scan in the background.
    """
    background_tasks.add_task(run_scan_task, send_telegram)
    return {
        "message": "Scan started in background",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/results", response_model=ScanResponse)
def get_latest_results():
    """
    Get the results of the last scan.
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
