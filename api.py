from fastapi import FastAPI, BackgroundTasks, HTTPException, Security, Depends, Query
from fastapi.security import APIKeyHeader
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import os
import logging
from datetime import datetime
from dotenv import load_dotenv

# Load env
load_dotenv()

# --- LOGGING CONFIG ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("screener_api.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Import existing logic
from main import WATCHLIST
from daily_swing_scan import get_swing_signals, send_telegram_report

# --- AUTH CONFIG ---
API_KEY = os.getenv("API_KEY")
API_KEY_HEADER_NAME = "access_token" 
api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)

async def get_api_key(
    api_key_header: str = Security(api_key_header),
    token: str = Query(None)
):
    """
    Validate API Key from either Header or Query Parameter.
    """
    if not API_KEY:
        logger.warning("⚠️ No API_KEY set in .env! API is unsecured.")
        return "unsecured_mode"
    
    # Check Header
    if api_key_header == API_KEY:
        return api_key_header
        
    # Check Query Param (e.g. ?token=123)
    if token == API_KEY:
        return token
        
    raise HTTPException(
        status_code=403, 
        detail="Could not validate credentials. Please provide correct 'access_token' header or '?token=' query parameter."
    )

app = FastAPI(
    title="Swing Trading Screener API",
    description="Production-Ready API for Trading Automation",
    version="1.1.0"
)

# CORS (Security Best Practice)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Update this to specific domains if you have a frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for latest results
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
    logger.info("Starting background scan...")
    try:
        signals = get_swing_signals(WATCHLIST)
        
        # Store results
        latest_signals = signals
        last_scan_time = datetime.now()
        
        if send_telegram:
            send_telegram_report(signals)
            
        logger.info(f"Scan complete. Found {len(signals)} signals.")
    except Exception as e:
        logger.error(f"Scan Error: {e}")

@app.post("/scan", response_model=dict)
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

@app.get("/portfolio", response_class=HTMLResponse)
def view_portfolio(api_key: str = Depends(get_api_key)):
    """
    Visualise current portfolio (Stocks & Options) with Real-Time PnL.
    Requires Auth (Header or ?token=YOUR_KEY).
    """
    import pandas as pd
    import yfinance as yf
    from trade_db import get_connection, get_balance
    
    try:
        conn = get_connection()
        # Using context manager for safety
        df = pd.read_sql_query("SELECT * FROM trades WHERE status = 'OPEN'", conn)
        conn.close()
        
        balance = get_balance()
        
        # Defaults
        total_invested = 0.0
        current_value = 0.0
        total_pnl = 0.0
        
        stocks_html = "<div class='alert alert-secondary'>No open stock positions.</div>"
        options_html = "<div class='alert alert-secondary'>No open option positions.</div>"
        
        if not df.empty:
            # Detect Type
            df['type'] = df['symbol'].apply(lambda x: 'OPTION' if 'CE' in x or 'PE' in x else 'STOCK')
            
            # Fetch Real-Time Prices
            tickers = [f"{s}.NS" for s in df['symbol'].unique()]
            try:
                # Batch download for speed
                data = yf.download(tickers, period="1d", progress=False)['Close']
                # If only one ticker, data is Series, make DataFrame
                if isinstance(data, pd.Series):
                     data = data.to_frame(name=tickers[0])
                live_prices = data.iloc[-1]
            except Exception as e:
                logger.error(f"Failed to fetch live prices: {e}")
                live_prices = {}
                
            # Calc PnL
            df['cmp'] = df['symbol'].apply(lambda x: live_prices.get(f"{x}.NS", 0.0))
            # Handle missing CMP (if market closed or yf fail, fallback to entry)
            df['cmp'] = df.apply(lambda row: row['entry_price'] if row['cmp'] == 0 or pd.isna(row['cmp']) else row['cmp'], axis=1)
            
            df['invested'] = df['entry_price'] * df['quantity']
            df['current_val'] = df['cmp'] * df['quantity']
            df['pnl'] = df['current_val'] - df['invested']
            df['pnl_pct'] = (df['pnl'] / df['invested']) * 100
            
            # Format for display
            df['pnl_display'] = df.apply(lambda row: f"<span class='fw-bold' style='color: {'#198754' if row['pnl']>=0 else '#dc3545'}'>{row['pnl']:+,.2f} ({row['pnl_pct']:+,.1f}%)</span>", axis=1)
            df['cmp_display'] = df['cmp'].apply(lambda x: f"₹{x:,.2f}")
            df['entry_display'] = df['entry_price'].apply(lambda x: f"₹{x:,.2f}")
            
            # Split
            stocks = df[df['type'] == 'STOCK'].copy()
            options = df[df['type'] == 'OPTION'].copy()
            
            # Aggregates
            total_invested = df['invested'].sum()
            current_value = df['current_val'].sum()
            total_pnl = current_value - total_invested
            
            # Generate Tables
            cols = ['symbol', 'quantity', 'entry_display', 'cmp_display', 'pnl_display', 'tp', 'sl']
            rename_map = {'symbol':'Symbol', 'quantity':'Qty', 'entry_display':'Entry', 'cmp_display':'CMP', 'pnl_display':'PnL', 'tp':'Target', 'sl':'Stop Loss'}
            
            if not stocks.empty:
                stocks_html = stocks[cols].rename(columns=rename_map).to_html(classes='table table-hover align-middle', escape=False, index=False)
                
            if not options.empty:
                options_html = options[cols].rename(columns=rename_map).to_html(classes='table table-hover align-middle', escape=False, index=False)

        # HTML Template
        from templates import get_portfolio_template
        pnl_color = "success" if total_pnl >= 0 else "danger"
        
        return get_portfolio_template(
            balance=balance,
            total_invested=total_invested,
            current_value=current_value,
            total_pnl=total_pnl,
            pnl_color=pnl_color,
            stocks_html=stocks_html,
            options_html=options_html
        )
        
    except Exception as e:
        logger.error(f"Error rendering portfolio: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
