
from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.api.deps import get_api_key
from app.db.database import get_connection
from app.services.analytics import calculate_strategy_metrics, get_benchmark_data, calculate_monthly_heatmap
import pandas as pd
import yfinance as yf
import json
from app.core.config import logger
from datetime import datetime

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.get("/portfolio", response_class=HTMLResponse)
def view_portfolio(request: Request, api_key: str = Depends(get_api_key)):
    """
    Visualise current portfolio (Stocks & Options) with Real-Time PnL.
    Requires Auth (Header or ?token=YOUR_KEY).
    """
    try:
        conn = get_connection()
        # Using context manager for safety
        with conn:
            # We fetch all columns including asset_type
            df = pd.read_sql_query("SELECT * FROM trades WHERE status = 'OPEN'", conn)
            
            # Fetch Real Strategy Wallets
            wallets_df = pd.read_sql_query("SELECT * FROM strategy_wallets", conn)
            
            # Fetch ALL trades logic (Only needed for Charts/Metrics now)
            all_trades_df = pd.read_sql_query("""
                SELECT * FROM trades ORDER BY entry_time DESC
            """, conn)

        # Convert to Dictionary for easy access
        strategy_capital = {}
        
        # Calculate Global Balance from Wallets
        balance = wallets_df['available_balance'].sum() if not wallets_df.empty else 0.0
        
        # Defaults
        total_invested = 0.0
        current_value = 0.0
        total_pnl = 0.0
        
        stocks_html = "<div class='alert alert-secondary'>No open stock positions.</div>"
        options_html = "<div class='alert alert-secondary'>No open option positions.</div>"
        
        if not df.empty:
            # Handle potential missing asset_type in DF from old tables if DB migration was tricky
            if 'asset_type' not in df.columns:
                df['asset_type'] = 'STOCK' # Default

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
            df['cmp'] = df['symbol'].apply(lambda x: live_prices.get(f"{x}.NS", 0.0) if isinstance(live_prices, (dict, pd.Series)) else 0.0)
            # Handle missing CMP
            df['cmp'] = df.apply(
                lambda row: row['entry_price'] if row['cmp'] == 0 or pd.isna(row['cmp']) else row['cmp'], 
                axis=1
            )
            
            df['invested'] = df['entry_price'] * df['quantity']
            df['current_val'] = df['cmp'] * df['quantity']
            df['pnl'] = df['current_val'] - df['invested']
            df['pnl_pct'] = (df['pnl'] / df['invested']) * 100
            
            # Format for display (HTML in DF)
            df['pnl_display'] = df.apply(lambda row: f"<span class='fw-bold' style='color: {'#198754' if row['pnl']>=0 else '#dc3545'}'>{row['pnl']:+,.2f} ({row['pnl_pct']:+,.1f}%)</span>", axis=1)
            df['cmp_display'] = df['cmp'].apply(lambda x: f"₹{x:,.2f}")
            df['entry_display'] = df['entry_price'].apply(lambda x: f"₹{x:,.2f}")
            
            # Aggregates
            total_invested = df['invested'].sum()
            current_value = df['current_val'].sum()
            total_pnl = current_value - total_invested
            
            # Filter Dataframes
            stocks_df = df[df['asset_type'] == 'STOCK'].copy()
            options_df = df[df['asset_type'] == 'OPTION'].copy()

            # Generate Tables
            cols = ['strategy', 'symbol', 'quantity', 'entry_display', 'cmp_display', 'pnl_display', 'tp', 'sl']
            rename_map = {'strategy': 'Strategy', 'symbol':'Symbol', 'quantity':'Qty', 'entry_display':'Entry', 'cmp_display':'CMP', 'pnl_display':'PnL', 'tp':'Target', 'sl':'Stop Loss'}
            
            if not stocks_df.empty:
                stocks_html = stocks_df[cols].rename(columns=rename_map).to_html(classes='table table-hover align-middle', escape=False, index=False)
            
            if not options_df.empty:
                # Use same cols for now
                options_html = options_df[cols].rename(columns=rename_map).to_html(classes='table table-hover align-middle', escape=False, index=False)

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
        metrics = {}
        heatmap = {}
        chart_data_json = "{}"
        
        try:
            closed_df = pd.DataFrame()
            
            if not all_trades_df.empty:
                if 'asset_type' not in all_trades_df.columns:
                    all_trades_df['asset_type'] = 'STOCK'
                    
                closed_df = all_trades_df[all_trades_df['status'] == 'CLOSED'].copy()
                
                realized_pnl = closed_df['pnl'].sum() if not closed_df.empty else 0.0
                
                # Calculate Risk:Reward ratio dynamically
                if not closed_df.empty:
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
                    # Added 'asset_type' -> 'Type'
                    display_cols = ['symbol', 'asset_type', 'strategy', 'quantity', 'entry_display', 'exit_display', 'rr_display', 'entry_date', 'exit_date', 'pnl_display', 'exit_reason']
                    rename_map = {
                        'symbol': 'Symbol',
                        'asset_type': 'Type',
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
                    
                    # Analytics (Chart, Metrics, Heatmap)
                    df_chart = closed_df.sort_values('exit_time').copy()
                    chart_data = {}
                    strategies = df_chart['strategy'].unique()
                    min_date = df_chart['exit_time'].min()
                    
                    for strat in strategies:
                        strat_df = df_chart[df_chart['strategy'] == strat]
                        base_capital = 100000.0
                        cum_equity = (strat_df['pnl'].cumsum() + base_capital).tolist()
                        dates = strat_df['exit_time'].tolist()
                        points = [{'x': str(d), 'y': p} for d, p in zip(dates, cum_equity)]
                        chart_data[strat] = points
                    
                    # Benchmark
                    if min_date:
                        nifty_data = get_benchmark_data(min_date)
                        if nifty_data:
                            chart_data['Nifty 50 (Benchmark)'] = nifty_data
                            
                    chart_data_json = json.dumps(chart_data)
                    metrics = calculate_strategy_metrics(closed_df)
                    heatmap = calculate_monthly_heatmap(closed_df)
                    
        except Exception as e:
            logger.error(f"Error fetching closed trades: {e}")
        
        # Prepare Summary Data for Client-Side Filtering
        summary_data = {}
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
        
        pnl_color = "success" if total_pnl >= 0 else "danger"
        heatmap_years = sorted(heatmap.keys(), reverse=True) if heatmap else []
        
        return templates.TemplateResponse("portfolio.html", {
            "request": request,
            "balance": balance,
            "total_invested": total_invested,
            "current_value": current_value,
            "total_pnl": total_pnl,
            "pnl_color": pnl_color,
            "now_str": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "stocks_html": stocks_html,
            "options_html": options_html,
            "closed_trades_html": closed_trades_html,
            "realized_pnl": realized_pnl,
            "chart_data_json": chart_data_json,
            "metrics": metrics,
            "heatmap": heatmap,
            "heatmap_years": heatmap_years,
            "strategy_capital": strategy_capital,
            "summary_json": summary_json
        })
        
    except Exception as e:
        logger.error(f"Error rendering portfolio: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")