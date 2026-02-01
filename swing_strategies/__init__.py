"""
Swing Trading Strategies Module

SuperTrend + Pivot Point Strategy
Inspired by CA Rachana Ranade's method

Holding period: 2-10 days
"""

import yfinance as yf
import pandas as pd
from typing import Dict, List, Optional

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


def fetch_stock_data(symbol: str, period: str = "6mo") -> pd.DataFrame:
    """
    Fetch daily OHLCV data from Yahoo Finance.
    
    Args:
        symbol: Stock symbol (without .NS suffix)
        period: Data period (default 6mo)
    
    Returns:
        Daily OHLCV DataFrame
    """
    if symbol.startswith("^"):
        ticker = symbol
    else:
        ticker = f"{symbol}.NS"
    try:
        # Suppress yfinance error output
        import sys
        import io
        suppress_stdout = io.StringIO()
        original_stdout = sys.stdout
        sys.stdout = suppress_stdout
        
        try:
            df = yf.download(ticker, period=period, interval="1d", progress=False, threads=False)
        finally:
            sys.stdout = original_stdout
        
        if df.empty:
            # Try BSE as fallback
            ticker_bse = f"{symbol}.BO"
            sys.stdout = suppress_stdout
            try:
                df = yf.download(ticker_bse, period=period, interval="1d", progress=False, threads=False)
            finally:
                sys.stdout = original_stdout
            
        if df.empty:
             # print(f"⚠️ No data for {symbol}")
             return pd.DataFrame()

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        df.columns = [c.lower() for c in df.columns]
        return df
        
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return pd.DataFrame()


def scan_symbol(symbol: str, period: str = "6mo") -> Optional[Dict]:
    """
    Fetch data and scan single symbol for signals.
    
    Args:
        symbol: Stock symbol
        period: Data period
    
    Returns:
        Signal dict if found, else None
    """
    df = fetch_stock_data(symbol, period)
    
    if df.empty or len(df) < 50:
        return None
    
    return swing_strategy_dispatcher(symbol, df)


def scan_stocks(symbols: List[str], period: str = "6mo") -> List[Dict]:
    """
    Scan multiple stocks and return actionable signals.
    
    Args:
        symbols: List of stock symbols
        period: Data period
    
    Returns:
        List of signals sorted by confidence
    """
    signals = []
    
    for symbol in symbols:
        try:
            signal = scan_symbol(symbol, period)
            if signal:
                signals.append(signal)
        except Exception as e:
            print(f"Error scanning {symbol}: {e}")
            continue
    
    # Sort by confidence
    signals.sort(key=lambda x: x['confidence'], reverse=True)
    
    return signals


def analyze_stock(symbol: str, period: str = "6mo") -> Dict:
    """
    Get detailed market analysis for a stock.
    
    Args:
        symbol: Stock symbol
        period: Data period
    
    Returns:
        Full analysis dict
    """
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
