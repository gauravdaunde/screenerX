import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

def calculate_strategy_metrics(df):
    """
    Calculate comprehensive metrics for each strategy:
    - Win Rate, Profit Factor, Max Drawdown, Avg Hold Time
    """
    if df.empty:
        return {}
        
    metrics = {}
    strategies = df['strategy'].unique()
    
    for strat in strategies:
        strat_df = df[df['strategy'] == strat].copy()
        strat_df = strat_df.sort_values('exit_time')
        
        # Basic Stats
        total_trades = len(strat_df)
        winners = strat_df[strat_df['pnl'] > 0]
        losers = strat_df[strat_df['pnl'] <= 0]
        
        win_rate = (len(winners) / total_trades) * 100 if total_trades > 0 else 0
        
        # Profit Factor
        gross_profit = winners['pnl'].sum()
        gross_loss = abs(losers['pnl'].sum())
        profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else float('inf')
        
        # Avg Hold Time
        # Ensure dates are datetime
        strat_df['exit_time'] = pd.to_datetime(strat_df['exit_time'])
        strat_df['entry_time'] = pd.to_datetime(strat_df['entry_time'])
        
        strat_df['hold_days'] = (strat_df['exit_time'] - strat_df['entry_time']).dt.total_seconds() / (24 * 3600)
        avg_hold_days = round(strat_df['hold_days'].mean(), 1)
        
        # Max Drawdown
        # We assume base capital 100k per strategy for standardized comparison
        base_capital = 100000.0
        strat_df['equity'] = base_capital + strat_df['pnl'].cumsum()
        strat_df['peak'] = strat_df['equity'].cummax()
        strat_df['drawdown'] = (strat_df['equity'] - strat_df['peak']) / strat_df['peak'] * 100
        max_dd = round(strat_df['drawdown'].min(), 2)
        
        metrics[strat] = {
            'total_trades': total_trades,
            'win_rate': round(win_rate, 1),
            'profit_factor': profit_factor,
            'avg_hold_days': avg_hold_days,
            'max_drawdown': max_dd,
            'total_pnl': strat_df['pnl'].sum()
        }
        
    return metrics

def get_benchmark_data(start_date, end_date=None):
    """
    Fetch Nifty 50 data and normalize to 100k base for comparison.
    Returns list of {'x': date, 'y': value}
    """
    if not end_date:
        end_date = datetime.now()
        
    try:
        # Buffer start date by a few days to ensure we cover the range
        start = pd.to_datetime(start_date) - timedelta(days=5)
        
        # Fetch Nifty 50
        ticker = "^NSEI" 
        df = yf.download(ticker, start=start, end=end_date, progress=False)
        
        if df.empty:
            return []
            
        # Normalize to 100k
        # We start normalization from the first actual trade date passed
        df = df[df.index >= pd.to_datetime(start_date)]
        
        if df.empty:
            return []
            
        start_price = df['Close'].iloc[0]
        # Handle MultiIndex if present (yfinance update)
        if isinstance(start_price, pd.Series):
             start_price = start_price.iloc[0]
             
        # Calculate factor
        factor = 100000.0 / start_price
        
        # Create series
        chart_data = []
        for index, row in df.iterrows():
            val = row['Close']
            if isinstance(val, pd.Series):
                val = val.iloc[0]
                
            norm_val = val * factor
            chart_data.append({
                'x': index.strftime('%Y-%m-%d %H:%M:%S'),
                'y': round(norm_val, 2)
            })
            
        return chart_data
        
    except Exception as e:
        logger.error(f"Benchmark error: {e}")
        return []

def calculate_monthly_heatmap(df):
    """
    Generate monthly PnL matrix.
    Returns: { '2025': {'Jan': 500, 'Feb': -200...}, ... }
    """
    if df.empty:
        return {}
        
    df = df.copy()
    df['exit_time'] = pd.to_datetime(df['exit_time'])
    df['year'] = df['exit_time'].dt.year
    df['month'] = df['exit_time'].dt.strftime('%b') # Jan, Feb..
    df['month_num'] = df['exit_time'].dt.month
    
    # Pivot
    heatmap = {}
    
    # Group by Year, Month
    monthly = df.groupby(['year', 'month', 'month_num'])['pnl'].sum().reset_index()
    monthly = monthly.sort_values(['year', 'month_num'])
    
    for _, row in monthly.iterrows():
        y = str(row['year'])
        m = row['month']
        val = row['pnl']
        
        if y not in heatmap:
            heatmap[y] = {}
        
        heatmap[y][m] = val
        
    return heatmap
