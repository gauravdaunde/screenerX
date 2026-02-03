from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from datetime import datetime
from app.api.deps import get_api_key
from app.schemas.scan import ScanResponse
from app.services.scanner import get_swing_signals, send_telegram_report
from app.core import state
from app.core.config import logger
from app.core.constants import WATCHLIST

router = APIRouter()

def run_scan_task(send_telegram: bool = True):
    logger.info("Starting background scan...")
    try:
        signals = get_swing_signals(WATCHLIST)
        
        # Store results
        state.latest_signals = signals
        state.last_scan_time = datetime.now()
        
        if send_telegram:
            send_telegram_report(signals)
            
        logger.info(f"Scan complete. Found {len(signals)} signals.")
    except Exception as e:
        logger.error(f"Scan Error: {e}")

@router.post("/scan", response_model=dict)
def trigger_scan(background_tasks: BackgroundTasks, send_telegram: bool = True, api_key: str = Depends(get_api_key)):
    """
    Trigger a manual scan in the background. Requires Auth.
    """
    background_tasks.add_task(run_scan_task, send_telegram)
    logger.info(f"Manual scan triggered via API")
    return {
        "message": "Scan started in background",
        "timestamp": datetime.now().isoformat()
    }

@router.get("/results", response_model=ScanResponse)
def get_latest_results(api_key: str = Depends(get_api_key)):
    """
    Get the results of the last scan. Requires Auth.
    """
    if state.last_scan_time is None:
        raise HTTPException(status_code=404, detail="No scan has been run yet.")
        
    return {
        "status": "success",
        "timestamp": state.last_scan_time.isoformat(),
        "signals_found": len(state.latest_signals) if state.latest_signals else 0,
        "signals": state.latest_signals
    }
