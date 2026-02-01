"""
Swing Trading - Indicator Calculator

Calculates all required indicators from OHLCV data.
"""

import pandas as pd
import numpy as np
from .models import MarketIndicators


def calculate_indicators(df: pd.DataFrame) -> MarketIndicators:
    """
    Calculate all technical indicators from OHLCV DataFrame.
    
    Args:
        df: DataFrame with columns: open, high, low, close, volume
        
    Returns:
        MarketIndicators object with all calculated values
    """
    # Ensure lowercase columns
    df.columns = [c.lower() for c in df.columns]
    
    close = df['close']
    high = df['high']
    low = df['low']
    
    # === EMAs ===
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean()
    
    # === RSI ===
    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    # === MACD ===
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    macd_histogram = macd - macd_signal
    
    # === ATR ===
    tr = pd.DataFrame({
        'hl': high - low,
        'hc': abs(high - close.shift(1)),
        'lc': abs(low - close.shift(1))
    }).max(axis=1)
    atr = tr.rolling(14).mean()
    
    # === Bollinger Bands ===
    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    bb_upper = bb_mid + (bb_std * 2)
    bb_lower = bb_mid - (bb_std * 2)
    bb_width = (bb_upper - bb_lower) / bb_mid
    
    # === Volume ===
    volume_avg = df['volume'].rolling(20).mean()
    
    # === Swing High/Low (5-bar pivots) ===
    swing_high = high.rolling(5, center=True).max().shift(-2).fillna(method='ffill')
    swing_low = low.rolling(5, center=True).min().shift(-2).fillna(method='ffill')
    
    # === Trend Detection ===
    curr_close = close.iloc[-1]
    curr_ema20 = ema20.iloc[-1]
    curr_ema50 = ema50.iloc[-1]
    curr_ema200 = ema200.iloc[-1]
    
    if curr_close > curr_ema20 > curr_ema50 > curr_ema200:
        trend = "UP"
    elif curr_close < curr_ema20 < curr_ema50 < curr_ema200:
        trend = "DOWN"
    else:
        trend = "SIDEWAYS"
    
    # Get current and previous values
    return MarketIndicators(
        close=curr_close,
        high=high.iloc[-1],
        low=low.iloc[-1],
        open=df['open'].iloc[-1],
        
        ema20=curr_ema20,
        ema50=curr_ema50,
        ema200=curr_ema200,
        
        rsi=rsi.iloc[-1],
        macd=macd.iloc[-1],
        macd_signal=macd_signal.iloc[-1],
        macd_histogram=macd_histogram.iloc[-1],
        
        atr=atr.iloc[-1],
        bb_upper=bb_upper.iloc[-1],
        bb_lower=bb_lower.iloc[-1],
        bb_width=bb_width.iloc[-1],
        
        volume=df['volume'].iloc[-1],
        volume_avg=volume_avg.iloc[-1],
        volume_ratio=df['volume'].iloc[-1] / volume_avg.iloc[-1] if volume_avg.iloc[-1] > 0 else 1,
        
        swing_high=swing_high.iloc[-1],
        swing_low=swing_low.iloc[-1],
        trend=trend,
        
        # Previous values
        prev_ema20=ema20.iloc[-2] if len(ema20) > 1 else curr_ema20,
        prev_ema50=ema50.iloc[-2] if len(ema50) > 1 else curr_ema50,
        prev_macd=macd.iloc[-2] if len(macd) > 1 else macd.iloc[-1],
        prev_macd_signal=macd_signal.iloc[-2] if len(macd_signal) > 1 else macd_signal.iloc[-1],
        prev_rsi=rsi.iloc[-2] if len(rsi) > 1 else rsi.iloc[-1]
    )
