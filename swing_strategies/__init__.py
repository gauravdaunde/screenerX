
"""
Swing Trading Strategies Module

SuperTrend + Pivot Point Strategy
Inspired by CA Rachana Ranade's method

Holding period: 2-10 days
"""

import pandas as pd
from typing import Dict, List, Optional
import os
import sys
import time
from datetime import datetime, timedelta
from dhanhq import dhanhq
from dotenv import load_dotenv
import yfinance as yf

from .supertrend_pivot import (
    supertrend_pivot_swing,
    swing_strategy_dispatcher,
    scan_stock,
    get_market_analysis,
    SwingSignal,
    calculate_supertrend,
    calculate_pivot_points,
    calculate_atr
)

# Load Env
load_dotenv(".env")
# Fallback to finding .env in root
if not os.getenv("DHAN_CLIENT_ID"):
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

def get_dhan_client():
    client_id = os.getenv("DHAN_CLIENT_ID")
    access_token = os.getenv("DHAN_ACCESS_TOKEN")
    if client_id and access_token:
        try:
            dhan = dhanhq(client_id, access_token)
            dhan.base_url = "https://api.dhan.co/v2"
            return dhan
        except Exception as e:
            print(f"Dhan Error: {e}")
    return None

def fetch_stock_data(symbol: str, period: str = "6mo") -> pd.DataFrame:
    """
    Fetch daily OHLCV data.
    Primary: Dhan API
    Fallback: Yahoo Finance (yfinance)
    
    Args:
        symbol: Stock symbol (without .NS suffix)
        period: Data period (default 6mo)
    
    Returns:
        Daily OHLCV DataFrame (lowercase columns)
    """
    df = pd.DataFrame()
    
    # --- 1. Try Dhan ---
    try:
        # Import SECURITY_IDS locally to avoid circular import
        try:
            from app.core.constants import SECURITY_IDS
        except ImportError:
            sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
            from app.core.constants import SECURITY_IDS

        dhan = get_dhan_client()
        security_id = SECURITY_IDS.get(symbol)
        
        if dhan and security_id:
            to_date = datetime.now().strftime('%Y-%m-%d')
            # Map period to days. 6mo ~ 180 days. 1y ~ 365 days.
            days = 180
            if period == "1y":
                days = 365
            elif period == "3mo":
                days = 90
            elif period == "1mo":
                 days = 30
                 
            from_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            res = dhan.historical_daily_data(
                security_id=security_id,
                exchange_segment='NSE_EQ',
                instrument_type='EQUITY',
                from_date=from_date,
                to_date=to_date
            )
            
            if res.get('status') == 'success' and res.get('data'):
                df_dhan = pd.DataFrame(res['data'])
                
                # Consistent timestamp parsing
                if 'start_Time' in df_dhan.columns:
                     df_dhan['datetime'] = pd.to_datetime(df_dhan['start_Time'], unit='s')
                elif 'timestamp' in df_dhan.columns:
                     df_dhan['datetime'] = pd.to_datetime(df_dhan['timestamp'], unit='s')
                elif 'k' in df_dhan.columns:
                     df_dhan['datetime'] = pd.to_datetime(df_dhan['k'], unit='s')
                else:
                     raise ValueError("Timestamp missing in Dhan response")
                     
                df_dhan = df_dhan.set_index('datetime')
                
                rename_map = {'o':'open','h':'high','l':'low','c':'close','v':'volume'}
                df_dhan = df_dhan.rename(columns=rename_map)
                
                # Lowercase columns
                df_dhan.columns = [c.lower() for c in df_dhan.columns]
                
                req = ['open','high','low','close']
                df_dhan = df_dhan[[c for c in req if c in df_dhan.columns]].astype(float)
                
                # Success checks
                if not df_dhan.empty and len(df_dhan) > 20:
                    return df_dhan

    except Exception as e:
        # print(f"Dhan fetch failed for {symbol}: {e}. Trying fallback...")
        pass

    # --- 2. Fallback to YFinance ---
    try:
        ticker = f"{symbol}.NS"
        df_yf = yf.download(ticker, period=period, interval="1d", progress=False)
        
        if not df_yf.empty:
            # Flatten MultiIndex if present
            if isinstance(df_yf.columns, pd.MultiIndex):
                df_yf.columns = df_yf.columns.get_level_values(0)
                
            df_yf.columns = [c.lower() for c in df_yf.columns]
            
            # Ensure proper index (Wait, yf.download usually sets Date index)
            # Just ensure types
            req = ['open','high','low','close']
            if all(c in df_yf.columns for c in req):
                return df_yf.astype(float)
                
    except Exception as e:
        print(f"YFinance fallback failed for {symbol}: {e}")

    return pd.DataFrame()


def scan_symbol(symbol: str, period: str = "6mo") -> Optional[Dict]:
    """Fetch data and scan single symbol for signals."""
    df = fetch_stock_data(symbol, period)
    
    if df.empty or len(df) < 50:
        return None
    
    return swing_strategy_dispatcher(symbol, df)


def scan_stocks(symbols: List[str], period: str = "6mo") -> List[Dict]:
    """Scan multiple stocks and return actionable signals."""
    signals = []
    
    for symbol in symbols:
        # Rate Limit
        time.sleep(1)
        
        try:
            signal = scan_symbol(symbol, period)
            if signal:
                signals.append(signal)
        except Exception as e:
            print(f"Error scanning {symbol}: {e}")
            continue
    
    signals.sort(key=lambda x: x['confidence'], reverse=True)
    return signals


def analyze_stock(symbol: str, period: str = "6mo") -> Dict:
    """Get detailed market analysis for a stock."""
    df = fetch_stock_data(symbol, period)
    
    if df.empty or len(df) < 50:
        return {"error": "Insufficient data", "symbol": symbol}
    
    return get_market_analysis(symbol, df)


# NIFTY 50 stocks (Full List)
NIFTY50 = [
    "RELIANCE", "TCS", "HDFCBANK", "ICICIBANK", "INFY", "HINDUNILVR",
    "ITC", "SBIN", "BHARTIARTL", "KOTAKBANK", "LT", "HCLTECH",
    "AXISBANK", "ASIANPAINT", "MARUTI", "SUNPHARMA", "TITAN",
    "BAJFINANCE", "WIPRO", "NTPC", "POWERGRID", "TECHM",
    "TATASTEEL", "ONGC", "COALINDIA", "DRREDDY", "CIPLA",
    "BRITANNIA", "HINDALCO", "JSWSTEEL", "ADANIENT", "ADANIPORTS",
    "APOLLOHOSP", "BAJAJFINSV", "BPCL", "DIVISLAB", "EICHERMOT",
    "GRASIM", "HEROMOTOCO", "HDFCLIFE", "INDUSINDBK", "LTIM",
    "M&M", "NESTLEIND", "SBILIFE", "TATACONSUM", "ULTRACEMCO", "BEL", "TRENT"
]


def scan_nifty50() -> List[Dict]:
    """Scan all Nifty 50 stocks."""
    return scan_stocks(NIFTY50)


__all__ = [
    # Main functions
    'supertrend_pivot_swing',
    'swing_strategy_dispatcher',
    'scan_stock',
    'get_market_analysis',
    
    # Convenience functions
    'fetch_stock_data',
    'scan_symbol',
    'scan_stocks',
    'analyze_stock',
    'scan_nifty50',
    
    # Indicators
    'calculate_supertrend',
    'calculate_pivot_points',
    'calculate_atr',
    
    # Data
    'SwingSignal',
    'NIFTY50'
]
