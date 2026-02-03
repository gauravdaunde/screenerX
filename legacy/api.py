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
    import json
    from trade_db import get_connection
    from portfolio_analytics import calculate_strategy_metrics, get_benchmark_data, calculate_monthly_heatmap
    
    try:
        conn = get_connection()
        # Using context manager for safety
        df = pd.read_sql_query("SELECT * FROM trades WHERE status = 'OPEN'", conn)
        
        # Fetch Real Strategy Wallets
        wallets_df = pd.read_sql_query("SELECT * FROM strategy_wallets", conn)
        
        # Convert to Dictionary for easy access
        # Key: Strategy Name, Value: Row Data
        strategy_capital = {}
        
        # Calculate Global Balance from Wallets
        balance = wallets_df['available_balance'].sum() if not wallets_df.empty else 0.0
        
        # Fetch ALL trades logic (Only needed for Charts/Metrics now, not for Capital Calc)
        # We can fetch this later only if needed, or keep it if used for analytics
        all_trades_df = pd.read_sql_query("""
            SELECT * FROM trades ORDER BY entry_time DESC
        """, conn)
        conn.close()
        
        # Defaults
        total_invested = 0.0
        current_value = 0.0
        total_pnl = 0.0
        
        stocks_html = "<div class='alert alert-secondary'>No open positions.</div>"
        if not df.empty:
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
            
            # Aggregates
            total_invested = df['invested'].sum()
            current_value = df['current_val'].sum()
            total_pnl = current_value - total_invested
            
            # Generate Tables
            cols = ['strategy', 'symbol', 'quantity', 'entry_display', 'cmp_display', 'pnl_display', 'tp', 'sl']
            rename_map = {'strategy': 'Strategy', 'symbol':'Symbol', 'quantity':'Qty', 'entry_display':'Entry', 'cmp_display':'CMP', 'pnl_display':'PnL', 'tp':'Target', 'sl':'Stop Loss'}
            
            stocks_html = df[cols].rename(columns=rename_map).to_html(classes='table table-hover align-middle', escape=False, index=False)

        # Build Strategy Capital Dict (Real Data from DB)
        if not wallets_df.empty:
            for _, row in wallets_df.iterrows():
                strat = row['strategy']
                cash = row['available_balance']
                allocation = row['allocation'] or 100000.0 # Fallback
                
                # Get stats from Open Trades
                s_invested = 0.0
                s_pos_count = 0
                
                if not df.empty:
                    strat_pos = df[df['strategy'] == strat]
                    if not strat_pos.empty:
                       s_invested = strat_pos['invested'].sum()
                       s_pos_count = len(strat_pos)
                
                # Metrics
                current_balance = cash + s_invested
                realized_pnl = current_balance - allocation
                
                strategy_capital[strat] = {
                    'base': allocation,
                    'realized_pnl': realized_pnl,
                    'current_balance': current_balance,
                    'invested': s_invested,
                    'available_cash': cash,
                    'open_positions': s_pos_count
                }

        # Fetch Closed Trades
        closed_trades_html = "<div class='alert alert-secondary'>No closed trades yet.</div>"
        realized_pnl = 0.0
        
        try:
            # Fetch ALL trades logic
            import sqlite3
            all_trades_df = pd.DataFrame()
            closed_df = pd.DataFrame()
            open_df = pd.DataFrame()
            
            conn = sqlite3.connect('trades.db')
            all_trades_df = pd.read_sql_query("""
                SELECT 
                    id,
                    symbol,
                    strategy,
                    signal_type,
                    entry_price,
                    quantity,
                    entry_time,
                    exit_price,
                    exit_time,
                    pnl,
                    exit_reason,
                    sl,
                    tp,
                    status
                FROM trades 
                ORDER BY entry_time DESC
            """, conn)
            conn.close()
            
            if not all_trades_df.empty:
                # Split
                closed_df = all_trades_df[all_trades_df['status'] == 'CLOSED'].copy()
                open_df = all_trades_df[all_trades_df['status'] == 'OPEN'].copy()
                
                realized_pnl = closed_df['pnl'].sum() if not closed_df.empty else 0.0
                
                # Calculate Risk:Reward ratio dynamically
                # Risk = Entry - SL, Reward = TP - Entry (for BUY trades)
                closed_df['risk'] = closed_df['entry_price'] - closed_df['sl']
                closed_df['reward'] = closed_df['tp'] - closed_df['entry_price']
                closed_df['rr_ratio'] = closed_df.apply(
                    lambda row: row['reward'] / row['risk'] if row['risk'] > 0 else 0, axis=1
                )
                closed_df['rr_display'] = closed_df['rr_ratio'].apply(
                    lambda x: f"1:{x:.1f}" if x > 0 else "N/A"
                )
                
                # Format columns for display
                closed_df['entry_display'] = closed_df['entry_price'].apply(lambda x: f"₹{x:,.2f}")
                closed_df['exit_display'] = closed_df['exit_price'].apply(lambda x: f"₹{x:,.2f}")
                closed_df['pnl_display'] = closed_df['pnl'].apply(
                    lambda x: f"<span class='fw-bold' style='color: {'#198754' if x >= 0 else '#dc3545'}'>₹{x:+,.2f}</span>"
                )
                
                # Format dates
                closed_df['entry_date'] = pd.to_datetime(closed_df['entry_time']).dt.strftime('%Y-%m-%d')
                closed_df['exit_date'] = pd.to_datetime(closed_df['exit_time']).dt.strftime('%Y-%m-%d')
                
                # Select and rename columns
                display_cols = ['symbol', 'strategy', 'quantity', 'entry_display', 'exit_display', 'rr_display', 'entry_date', 'exit_date', 'pnl_display', 'exit_reason']
                rename_map = {
                    'symbol': 'Symbol',
                    'strategy': 'Strategy',
                    'quantity': 'Qty',
                    'entry_display': 'Entry',
                    'exit_display': 'Exit',
                    'rr_display': 'R:R',
                    'entry_date': 'Entry Date',
                    'exit_date': 'Exit Date',
                    'pnl_display': 'PnL',
                    'exit_reason': 'Reason'
                }
                
                closed_trades_html = closed_df[display_cols].rename(columns=rename_map).to_html(
                    classes='table table-hover align-middle', 
                    escape=False, 
                    index=False
                )
        except Exception as e:
            logger.error(f"Error fetching closed trades: {e}")
        
        if not all_trades_df.empty:
             try:
                # 1. Chart Data (Equity Curves)
                # Use closed_df for chart
                df_chart = closed_df.sort_values('exit_time').copy()
                chart_data = {}
                strategies = df_chart['strategy'].unique()
                
                min_date = df_chart['exit_time'].min() if not df_chart.empty else None
                
                if not df_chart.empty:
                    for strat in strategies:
                        strat_df = df_chart[df_chart['strategy'] == strat]
                        # Start with 100k base capital
                        base_capital = 100000.0
                        
                        # Calculate cumulative PnL + Base
                        cum_equity = (strat_df['pnl'].cumsum() + base_capital).tolist()
                        dates = strat_df['exit_time'].tolist()
                        
                        # Create XY points
                        points = [{'x': str(d), 'y': p} for d, p in zip(dates, cum_equity)]
                        chart_data[strat] = points
                    
                    # 2. Benchmark (Nifty 50)
                    if min_date:
                        nifty_data = get_benchmark_data(min_date)
                        if nifty_data:
                            chart_data['Nifty 50 (Benchmark)'] = nifty_data
                        
                chart_data_json = json.dumps(chart_data)
                
                # 3. Strategy Metrics
                metrics = calculate_strategy_metrics(closed_df)
                
                # 4. Monthly Heatmap
                heatmap = calculate_monthly_heatmap(closed_df)
                
                # 5. Strategy Capital - Already calculated
                
             except Exception as e:
                 logger.error(f"Error preparing analytics: {e}")

        # Prepare Summary Data for Client-Side Filtering
        summary_data = {}
        # strategy_capital keys cover all relevant strategies
        for strat, cap_data in strategy_capital.items():
            s_cash = cap_data.get('available_cash', 0.0)
            
            s_invested = 0.0
            s_current_val = 0.0
            
            if not df.empty:
                strat_pos = df[df['strategy'] == strat]
                if not strat_pos.empty:
                    s_invested = strat_pos['invested'].sum()
                    s_current_val = strat_pos['current_val'].sum()
            
            s_pnl = s_current_val - s_invested
            
            summary_data[strat] = {
                'cash': s_cash,
                'invested': s_invested,
                'current_value': s_current_val,
                'pnl': s_pnl
            }
            
        summary_json = json.dumps(summary_data)

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
            closed_trades_html=closed_trades_html,
            realized_pnl=realized_pnl,
            chart_data_json=chart_data_json,
            metrics=metrics,
            heatmap=heatmap,
            strategy_capital=strategy_capital,
            summary_json=summary_json
        )
        
    except Exception as e:
        logger.error(f"Error rendering portfolio: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

if __name__ == "__main__":
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
