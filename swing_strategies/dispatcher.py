"""
Swing Strategy Dispatcher

Main entry point for the swing trading system.
Analyzes a stock and returns the best trading signal.
"""

import pandas as pd
from typing import List, Dict, Optional
from .models import SwingSignal, MarketIndicators
from .indicators import calculate_indicators
from .strategies import ALL_STRATEGIES


def swing_strategy_dispatcher(df: pd.DataFrame, symbol: str) -> Dict:
    """
    Main dispatcher for swing trading strategies.
    
    Args:
        df: OHLCV DataFrame (daily candles, min 200 bars)
        symbol: Stock symbol
        
    Returns:
        Best signal as dictionary
    """
    # Calculate all indicators
    try:
        indicators = calculate_indicators(df)
    except Exception as e:
        return {
            "symbol": symbol,
            "signal": "HOLD",
            "confidence": 0,
            "reason": f"Error calculating indicators: {e}"
        }
    
    # Run all strategies
    signals = []
    
    for strategy_func in ALL_STRATEGIES:
        try:
            signal = strategy_func(symbol, indicators)
            if signal.signal != "HOLD" and signal.confidence > 0.5:
                signals.append(signal)
        except Exception as e:
            continue
    
    # No valid signals
    if not signals:
        return {
            "symbol": symbol,
            "signal": "HOLD",
            "confidence": 0,
            "reason": "No high-confidence signals"
        }
    
    # Sort by confidence and return best
    signals.sort(key=lambda x: x.confidence, reverse=True)
    best_signal = signals[0]
    
    return best_signal.to_dict()


def scan_all_strategies(df: pd.DataFrame, symbol: str) -> List[Dict]:
    """
    Run all strategies and return all signals (for analysis).
    
    Args:
        df: OHLCV DataFrame
        symbol: Stock symbol
        
    Returns:
        List of all signals (including HOLD)
    """
    indicators = calculate_indicators(df)
    
    signals = []
    for strategy_func in ALL_STRATEGIES:
        try:
            signal = strategy_func(symbol, indicators)
            signals.append(signal.to_dict())
        except:
            continue
    
    return signals


def get_market_analysis(df: pd.DataFrame, symbol: str) -> Dict:
    """
    Get comprehensive market analysis for a symbol.
    
    Returns indicators + signals.
    """
    indicators = calculate_indicators(df)
    
    # Get all signals
    all_signals = scan_all_strategies(df, symbol)
    
    # Filter actionable signals
    actionable = [s for s in all_signals if s['signal'] != 'HOLD' and s['confidence'] > 0.5]
    
    return {
        "symbol": symbol,
        "timestamp": pd.Timestamp.now().isoformat(),
        
        "market_state": {
            "price": round(indicators.close, 2),
            "trend": indicators.trend,
            "rsi": round(indicators.rsi, 1),
            "macd_histogram": round(indicators.macd_histogram, 2),
            "volume_ratio": round(indicators.volume_ratio, 2),
            "atr": round(indicators.atr, 2),
            "bb_width": round(indicators.bb_width, 4)
        },
        
        "ema_structure": {
            "ema20": round(indicators.ema20, 2),
            "ema50": round(indicators.ema50, 2),
            "ema200": round(indicators.ema200, 2),
            "price_vs_ema20": round((indicators.close - indicators.ema20) / indicators.close * 100, 2),
            "price_vs_ema50": round((indicators.close - indicators.ema50) / indicators.close * 100, 2)
        },
        
        "swing_levels": {
            "swing_high": round(indicators.swing_high, 2),
            "swing_low": round(indicators.swing_low, 2),
            "distance_to_high": round((indicators.swing_high - indicators.close) / indicators.close * 100, 2),
            "distance_to_low": round((indicators.close - indicators.swing_low) / indicators.close * 100, 2)
        },
        
        "signals": actionable,
        "best_signal": actionable[0] if actionable else None,
        "signal_count": len(actionable)
    }
