"""
SuperTrend + Pivot Point Swing Trading Strategy
Inspired by CA Rachana Ranade's method

Combines:
- SuperTrend indicator (trend direction)
- Pivot Point breakout levels (entry trigger)

Holding period: 2-10 days (SWING)
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass
class SwingSignal:
    """Standardized signal output format."""
    symbol: str
    strategy_name: str
    signal: str  # BUY, SELL, HOLD
    confidence: float
    entry_type: str
    stop_loss: float
    target: float
    holding_type: str
    reason: str
    entry_price: float = 0
    risk_reward: float = 0
    
    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "strategy_name": self.strategy_name,
            "signal": self.signal,
            "confidence": round(self.confidence, 2),
            "entry_type": self.entry_type,
            "stop_loss": round(self.stop_loss, 2),
            "target": round(self.target, 2),
            "holding_type": self.holding_type,
            "reason": self.reason,
            "entry_price": round(self.entry_price, 2),
            "risk_reward": round(self.risk_reward, 2)
        }


# =============================================================================
# INDICATOR CALCULATIONS
# =============================================================================

def calculate_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> Tuple[pd.Series, pd.Series]:
    """
    Calculate SuperTrend indicator.
    
    Returns:
        supertrend: SuperTrend line values
        direction: 1 for bullish (green), -1 for bearish (red)
    """
    high = df['high']
    low = df['low']
    close = df['close']
    
    # Calculate ATR
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    
    # Calculate basic bands
    hl2 = (high + low) / 2
    upper_band = hl2 + (multiplier * atr)
    lower_band = hl2 - (multiplier * atr)
    
    # Initialize SuperTrend
    supertrend = pd.Series(index=df.index, dtype=float)
    direction = pd.Series(index=df.index, dtype=float)
    
    # First valid value
    supertrend.iloc[period] = upper_band.iloc[period]
    direction.iloc[period] = -1
    
    for i in range(period + 1, len(df)):
        # Previous values
        prev_supertrend = supertrend.iloc[i-1]
        prev_close = close.iloc[i-1]
        curr_close = close.iloc[i]
        prev_direction = direction.iloc[i-1]
        
        curr_upper = upper_band.iloc[i]
        curr_lower = lower_band.iloc[i]
        prev_upper = upper_band.iloc[i-1]
        prev_lower = lower_band.iloc[i-1]
        
        # Calculate final bands
        if curr_lower > prev_lower or prev_close < prev_lower:
            final_lower = curr_lower
        else:
            final_lower = prev_lower
            
        if curr_upper < prev_upper or prev_close > prev_upper:
            final_upper = curr_upper
        else:
            final_upper = prev_upper
        
        # Determine SuperTrend and direction
        if prev_supertrend == prev_upper:
            if curr_close > final_upper:
                supertrend.iloc[i] = final_lower
                direction.iloc[i] = 1  # Bullish
            else:
                supertrend.iloc[i] = final_upper
                direction.iloc[i] = -1  # Bearish
        else:
            if curr_close < final_lower:
                supertrend.iloc[i] = final_upper
                direction.iloc[i] = -1  # Bearish
            else:
                supertrend.iloc[i] = final_lower
                direction.iloc[i] = 1  # Bullish
    
    return supertrend, direction


def calculate_pivot_points(df: pd.DataFrame) -> Dict[str, float]:
    """
    Calculate Daily Pivot Points using previous day's data.
    
    Returns dict with: P, R1, R2, R3, S1, S2, S3
    """
    if len(df) < 2:
        return {}
    
    # Use previous day's OHLC
    prev_high = df['high'].iloc[-2]
    prev_low = df['low'].iloc[-2]
    prev_close = df['close'].iloc[-2]
    
    # Calculate Pivot Point
    pivot = (prev_high + prev_low + prev_close) / 3
    
    # Resistance levels
    r1 = (2 * pivot) - prev_low
    r2 = pivot + (prev_high - prev_low)
    r3 = prev_high + 2 * (pivot - prev_low)
    
    # Support levels
    s1 = (2 * pivot) - prev_high
    s2 = pivot - (prev_high - prev_low)
    s3 = prev_low - 2 * (prev_high - pivot)
    
    return {
        'P': pivot,
        'R1': r1, 'R2': r2, 'R3': r3,
        'S1': s1, 'S2': s2, 'S3': s3
    }


def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    """Calculate current ATR value."""
    high = df['high']
    low = df['low']
    close = df['close']
    
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    
    return atr.iloc[-1]


def get_swing_points(df: pd.DataFrame, lookback: int = 10) -> Tuple[float, float]:
    """Get recent swing high and swing low."""
    recent = df.tail(lookback)
    return recent['high'].max(), recent['low'].min()


def get_volume_ratio(df: pd.DataFrame, period: int = 20) -> float:
    """Calculate current volume vs average volume ratio."""
    if 'volume' not in df.columns:
        return 1.0
    
    avg_volume = df['volume'].rolling(window=period).mean().iloc[-1]
    current_volume = df['volume'].iloc[-1]
    
    if avg_volume > 0:
        return current_volume / avg_volume
    return 1.0


# =============================================================================
# MAIN STRATEGY
# =============================================================================

def supertrend_pivot_swing(symbol: str, df: pd.DataFrame) -> SwingSignal:
    """
    SuperTrend + Pivot Point Swing Trading Strategy
    
    Entry conditions:
    - BUY: SuperTrend bullish + Close > R1 + Volume confirmation
    - SELL: SuperTrend bearish + Close < S1 + Volume confirmation
    
    Args:
        symbol: Stock symbol
        df: Daily OHLCV DataFrame (minimum 50 rows)
    
    Returns:
        SwingSignal with trade details
    """
    
    # Validate data
    if len(df) < 50:
        return SwingSignal(
            symbol=symbol,
            strategy_name="supertrend_pivot_swing",
            signal="HOLD",
            confidence=0,
            entry_type="NONE",
            stop_loss=0,
            target=0,
            holding_type="SWING",
            reason="Insufficient data"
        )
    
    # Normalize column names
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]
    
    # Calculate indicators
    supertrend, direction = calculate_supertrend(df, period=10, multiplier=3.0)
    pivots = calculate_pivot_points(df)
    atr = calculate_atr(df, period=14)
    swing_high, swing_low = get_swing_points(df, lookback=10)
    volume_ratio = get_volume_ratio(df)
    
    # Current values
    close = df['close'].iloc[-1]
    high = df['high'].iloc[-1]
    low = df['low'].iloc[-1]
    open_price = df['open'].iloc[-1]
    st_value = supertrend.iloc[-1]
    st_direction = direction.iloc[-1]
    prev_close = df['close'].iloc[-2]
    
    # Candle analysis
    candle_body = abs(close - open_price)
    candle_range = high - low
    body_ratio = candle_body / candle_range if candle_range > 0 else 0
    
    # Check if bullish/bearish candle
    is_bullish_candle = close > open_price
    is_bearish_candle = close < open_price
    
    # Close near high/low
    close_near_high = (high - close) / candle_range < 0.25 if candle_range > 0 else False
    close_near_low = (close - low) / candle_range < 0.25 if candle_range > 0 else False
    
    # Initialize signal variables
    signal = "HOLD"
    confidence = 0.0
    reasons = []
    stop_loss = 0.0
    target = 0.0
    
    # ==========================================================================
    # AVOID CONDITIONS
    # ==========================================================================
    
    # Low volume
    if volume_ratio < 0.7:
        return SwingSignal(
            symbol=symbol,
            strategy_name="supertrend_pivot_swing",
            signal="HOLD",
            confidence=0,
            entry_type="NONE",
            stop_loss=0,
            target=0,
            holding_type="SWING",
            reason="Volume too low (<0.7x avg)"
        )
    
    # Low ATR (no volatility)
    avg_price = df['close'].mean()
    atr_pct = (atr / avg_price) * 100
    if atr_pct < 0.5:
        return SwingSignal(
            symbol=symbol,
            strategy_name="supertrend_pivot_swing",
            signal="HOLD",
            confidence=0,
            entry_type="NONE",
            stop_loss=0,
            target=0,
            holding_type="SWING",
            reason="ATR too low (no volatility)"
        )
    
    # Price stuck between P and R1/S1
    if pivots:
        in_no_trade_zone = pivots['S1'] < close < pivots['R1']
        if in_no_trade_zone and body_ratio < 0.5:
            return SwingSignal(
                symbol=symbol,
                strategy_name="supertrend_pivot_swing",
                signal="HOLD",
                confidence=0,
                entry_type="NONE",
                stop_loss=0,
                target=0,
                holding_type="SWING",
                reason="Price in no-trade zone (between S1 and R1)"
            )
    
    # Large wicks (indecision)
    upper_wick = high - max(open_price, close)
    lower_wick = min(open_price, close) - low
    wick_ratio = (upper_wick + lower_wick) / candle_range if candle_range > 0 else 0
    if wick_ratio > 0.7:
        return SwingSignal(
            symbol=symbol,
            strategy_name="supertrend_pivot_swing",
            signal="HOLD",
            confidence=0,
            entry_type="NONE",
            stop_loss=0,
            target=0,
            holding_type="SWING",
            reason="Large wicks (indecision candle)"
        )
    
    # ==========================================================================
    # BUY SIGNAL
    # ==========================================================================
    
    if st_direction == 1 and pivots:  # SuperTrend Bullish
        r1 = pivots['R1']
        r2 = pivots['R2']
        
        # Breakout above R1
        if close > r1 and prev_close <= r1:
            signal = "BUY"
            confidence = 0.5
            reasons.append(f"Breakout above R1 ({r1:.0f})")
            
            # Confidence boosters
            if is_bullish_candle:
                confidence += 0.1
                reasons.append("Bullish candle")
            
            if close_near_high:
                confidence += 0.1
                reasons.append("Close near high")
            
            if volume_ratio > 1.5:
                confidence += 0.15
                reasons.append(f"Strong volume ({volume_ratio:.1f}x)")
            elif volume_ratio > 1.2:
                confidence += 0.1
                reasons.append("Volume confirmation")
            
            if body_ratio > 0.6:
                confidence += 0.1
                reasons.append("Strong candle body")
            
            # Trend strength
            trend_slope = (df['close'].iloc[-1] - df['close'].iloc[-5]) / df['close'].iloc[-5] * 100
            if trend_slope > 2:
                confidence += 0.1
                reasons.append("Strong trend slope")
            
            # ATR expanding
            prev_atr = calculate_atr(df.iloc[:-1], period=14)
            if atr > prev_atr * 1.1:
                confidence += 0.05
                reasons.append("ATR expanding")
            
            # Stop Loss: Min of SuperTrend, swing low, entry - 1.5*ATR
            stop_options = [
                st_value,
                swing_low,
                close - (1.5 * atr)
            ]
            stop_loss = max(stop_options)  # Tightest reasonable stop
            
            # Target: R2 or 3R minimum (improved R:R)
            risk = close - stop_loss
            r2_target = r2
            three_r_target = close + (3 * risk)  # 3R instead of 2R
            target = max(r2_target, three_r_target)
            
    # ==========================================================================
    # SELL SIGNAL
    # ==========================================================================
    
    elif st_direction == -1 and pivots:  # SuperTrend Bearish
        s1 = pivots['S1']
        s2 = pivots['S2']
        
        # Breakdown below S1
        if close < s1 and prev_close >= s1:
            signal = "SELL"
            confidence = 0.5
            reasons.append(f"Breakdown below S1 ({s1:.0f})")
            
            if is_bearish_candle:
                confidence += 0.1
                reasons.append("Bearish candle")
            
            if close_near_low:
                confidence += 0.1
                reasons.append("Close near low")
            
            if volume_ratio > 1.5:
                confidence += 0.15
                reasons.append(f"Strong volume ({volume_ratio:.1f}x)")
            elif volume_ratio > 1.2:
                confidence += 0.1
                reasons.append("Volume confirmation")
            
            if body_ratio > 0.6:
                confidence += 0.1
                reasons.append("Strong candle body")
            
            # Trend slope
            trend_slope = (df['close'].iloc[-1] - df['close'].iloc[-5]) / df['close'].iloc[-5] * 100
            if trend_slope < -2:
                confidence += 0.1
                reasons.append("Strong downtrend")
            
            # Stop Loss
            stop_options = [
                st_value,
                swing_high,
                close + (1.5 * atr)
            ]
            stop_loss = min(stop_options)
            
            # Target: 3R minimum (improved R:R)
            risk = stop_loss - close
            s2_target = s2
            three_r_target = close - (3 * risk)
            target = min(s2_target, three_r_target)
    
    # ==========================================================================
    # Confidence penalties
    # ==========================================================================
    
    if signal != "HOLD":
        # Weak breakout candle
        if body_ratio < 0.4:
            confidence -= 0.1
            reasons.append("⚠️ Weak candle structure")
        
        # Price near resistance cluster
        if pivots:
            near_r2 = abs(close - pivots['R2']) / close < 0.01
            near_s2 = abs(close - pivots['S2']) / close < 0.01
            if near_r2 or near_s2:
                confidence -= 0.1
                reasons.append("⚠️ Near major pivot level")
    
    # Clamp confidence
    confidence = max(0, min(1.0, confidence))
    
    # Calculate risk-reward
    if signal != "HOLD" and stop_loss > 0:
        risk = abs(close - stop_loss)
        reward = abs(target - close)
        risk_reward = reward / risk if risk > 0 else 0
    else:
        risk_reward = 0
    
    return SwingSignal(
        symbol=symbol,
        strategy_name="supertrend_pivot_swing",
        signal=signal if confidence >= 0.7 else "HOLD",  # Higher threshold for better quality
        confidence=confidence,
        entry_type="BREAKOUT" if signal != "HOLD" else "NONE",
        stop_loss=stop_loss,
        target=target,
        holding_type="SWING",
        reason="; ".join(reasons) if reasons else "No signal",
        entry_price=close,
        risk_reward=risk_reward
    )


# =============================================================================
# DISPATCHER
# =============================================================================

def swing_strategy_dispatcher(symbol: str, df: pd.DataFrame) -> Optional[Dict]:
    """
    Main dispatcher for swing strategy.
    
    Only returns signal if confidence > 0.6
    
    Args:
        symbol: Stock symbol
        df: Daily OHLCV DataFrame
    
    Returns:
        Signal dict or None
    """
    signal = supertrend_pivot_swing(symbol, df)
    
    # Return signal if valid (cutoff decreased to 0.5 to allow external filtering)
    if signal.signal != "HOLD" and signal.confidence >= 0.5:
        return signal.to_dict()
    
    return None


def scan_stock(symbol: str, df: pd.DataFrame) -> Optional[Dict]:
    """Convenience wrapper for scanning a single stock."""
    return swing_strategy_dispatcher(symbol, df)


def get_market_analysis(symbol: str, df: pd.DataFrame) -> Dict:
    """
    Get full market analysis including indicators.
    
    Returns comprehensive analysis dict.
    """
    if len(df) < 50:
        return {"error": "Insufficient data"}
    
    df = df.copy()
    df.columns = [c.lower() for c in df.columns]
    
    supertrend, direction = calculate_supertrend(df)
    pivots = calculate_pivot_points(df)
    atr = calculate_atr(df)
    swing_high, swing_low = get_swing_points(df)
    volume_ratio = get_volume_ratio(df)
    
    signal = supertrend_pivot_swing(symbol, df)
    
    return {
        "symbol": symbol,
        "price": df['close'].iloc[-1],
        "supertrend": {
            "value": supertrend.iloc[-1],
            "direction": "BULLISH" if direction.iloc[-1] == 1 else "BEARISH"
        },
        "pivots": pivots,
        "atr": atr,
        "swing_high": swing_high,
        "swing_low": swing_low,
        "volume_ratio": volume_ratio,
        "signal": signal.to_dict()
    }
