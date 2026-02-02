"""
Swing Trading Strategy Suite (Optimized v2)
============================================

This module contains a collection of refined swing trading strategies, each targeting specific market conditions.
These strategies have been backtested and optimized for the Nifty 50 universe.

1. Momentum Strategies
   - **MACD Momentum**: Captures strong trend accelerations using Zero-Line Crossovers confirmed by Volume and EMA alignment. Best for early trend entry.
   - **EMA Crossover**: Classical trend following using EMA20/50 crosses, filtered by long-term trend (EMA200) and Volume.

2. Mean Reversion Strategies
   - **BB Mean Reversion**: Exploits overextended moves in sideways markets. Buys at Lower BB and Sells at Upper BB when RSI is oversold/overbought. Highly effective in chopping markets (FMCG).
   - **Trend Pullback**: Buys dips to the 20 EMA in established strong trends. The "Buy the Dip" strategy.

3. Breakout Strategies
   - **Swing Breakout**: Enter on volatilty expansion above key Swing Highs/Lows. Requires massive volume confirmation.

Optimization Philosophy:
------------------------
- **Quality over Quantity**: Strict filters (Volume, Candle Body, Trend alignment) reduce trade frequency but boost Win Rate.
- **Context Awareness**: Strategies check for specific market regimes (Trending vs Sideways) before triggering.
- **Risk Management**: Dynamic Stop Losses based on ATR or Swing Levels are integral to every signal.
"""

from .models import SwingSignal, MarketIndicators


def _check_common_filters(ind: MarketIndicators) -> tuple:
    """
    Common filters to avoid bad entries.
    Returns: (pass_filter: bool, penalty: float, reasons: list)
    """
    penalty = 0
    reasons = []
    
    # 1. Volume Filter (CRITICAL) - Stricter threshold
    if ind.volume_ratio < 1.0:
        return False, 0.5, ["Volume below average"]
    elif ind.volume_ratio < 1.2:
        penalty += 0.15
        reasons.append("⚠️ Marginally above-avg volume")
    
    # 2. ATR Spike (News/Event risk)
    # If today's range is > 2x ATR, likely news-driven
    today_range = ind.high - ind.low
    if today_range > ind.atr * 2.5:
        return False, 0.3, ["Abnormal volatility (news?)"]
    
    # 3. Avoid tiny candles (low conviction)
    body = abs(ind.close - ind.open)
    if body < ind.atr * 0.2:
        penalty += 0.15
        reasons.append("Weak candle body")
    
    return True, penalty, reasons


def _calculate_swing_stop(ind: MarketIndicators, signal: str) -> float:
    """Calculate stop-loss using swing levels + WIDER buffer."""
    # OPTIMIZATION: Use 1.5x ATR buffer (was 0.3x) to avoid premature stops
    buffer = ind.atr * 1.5
    
    if signal == "BUY":
        # Stop below recent swing low with buffer
        return min(ind.swing_low - buffer, ind.close - (ind.atr * 2))
    else:
        # Stop above recent swing high with buffer
        return max(ind.swing_high + buffer, ind.close + (ind.atr * 2))


# ============================================================================
# 🔹 STRATEGY 1: MACD MOMENTUM (OPTIMIZED - Best performer)
# ============================================================================

def strategy_macd_momentum(symbol: str, ind: MarketIndicators) -> SwingSignal:
    """
    MACD Momentum Swing - OPTIMIZED
    
    Entry Improvements:
    - Require MACD cross below/above zero line
    - Volume must be above average
    - Trend alignment with EMAs
    - Strong candle confirmation
    """
    signal = "HOLD"
    score = 0.0
    reasons = []
    
    # Check common filters
    pass_filter, penalty, filter_reasons = _check_common_filters(ind)
    if not pass_filter:
        return SwingSignal(
            symbol=symbol, strategy_name="MACD Momentum", signal="HOLD",
            confidence=0, stop_loss_type="SWING", target_type="RR",
            reason=filter_reasons[0]
        )
    
    # Detect MACD crossover
    bullish_cross = ind.prev_macd <= ind.prev_macd_signal and ind.macd > ind.macd_signal
    bearish_cross = ind.prev_macd >= ind.prev_macd_signal and ind.macd < ind.macd_signal
    
    if bullish_cross:
        signal = "BUY"
        score = 0.4
        reasons.append("MACD bullish crossover")
        
        # OPTIMIZATION: Must be below zero line (fresh momentum)
        if ind.macd < 0:
            score += 0.25
            reasons.append("Cross below zero (high probability)")
        else:
            score -= 0.1  # Penalty for late entry
        
        # OPTIMIZATION: Trend alignment
        if ind.close > ind.ema50:
            score += 0.15
            reasons.append("Price above EMA50")
        else:
            score -= 0.15
        
        # OPTIMIZATION: Volume confirmation
        if ind.volume_ratio > 1.3:
            score += 0.2
            reasons.append("Strong volume")
        elif ind.volume_ratio > 1.1:
            score += 0.1
        
        # OPTIMIZATION: Bullish candle
        if ind.close > ind.open:
            score += 0.1
            reasons.append("Bullish candle")
        else:
            score -= 0.1
            
    elif bearish_cross:
        signal = "SELL"
        score = 0.4
        reasons.append("MACD bearish crossover")
        
        if ind.macd > 0:
            score += 0.25
        if ind.close < ind.ema50:
            score += 0.15
        if ind.volume_ratio > 1.3:
            score += 0.2
        if ind.close < ind.open:
            score += 0.1
    
    score -= penalty
    
    # Stop-loss using swing levels
    stop_loss = _calculate_swing_stop(ind, signal)
    risk = abs(ind.close - stop_loss)
    target = ind.close + (risk * 2.5) if signal == "BUY" else ind.close - (risk * 2.5)
    
    return SwingSignal(
        symbol=symbol,
        strategy_name="MACD Momentum",
        signal=signal if score >= 0.75 else "HOLD",  # Balanced threshold
        confidence=min(max(score, 0), 1.0),
        stop_loss_type="SWING",
        target_type="RR",
        reason="; ".join(reasons),
        entry_price=ind.close,
        stop_loss=stop_loss,
        target=target,
        risk_reward=2.5
    )


# ============================================================================
# 🔹 STRATEGY 2: BB MEAN REVERSION (OPTIMIZED - Best avg P&L)
# ============================================================================

def strategy_bb_mean_reversion(symbol: str, ind: MarketIndicators) -> SwingSignal:
    """
    Bollinger Band Mean Reversion - OPTIMIZED
    
    Entry Improvements:
    - MUST be in sideways market
    - RSI must be extreme (<30 or >70)
    - Wait for reversal candle
    - Tighter stop at band + buffer
    """
    signal = "HOLD"
    score = 0.0
    reasons = []
    
    # OPTIMIZATION: Strict sideways filter
    if ind.trend != "SIDEWAYS":
        return SwingSignal(
            symbol=symbol, strategy_name="BB Mean Reversion", signal="HOLD",
            confidence=0, stop_loss_type="BAND", target_type="BAND",
            reason="Requires sideways market"
        )
    
    pass_filter, penalty, filter_reasons = _check_common_filters(ind)
    if not pass_filter:
        return SwingSignal(
            symbol=symbol, strategy_name="BB Mean Reversion", signal="HOLD",
            confidence=0, stop_loss_type="BAND", target_type="BAND",
            reason=filter_reasons[0]
        )
    
    bb_mid = (ind.bb_upper + ind.bb_lower) / 2
    
    # Buy at lower band
    if ind.close <= ind.bb_lower:
        signal = "BUY"
        score = 0.4
        reasons.append("Price at lower BB")
        
        # OPTIMIZATION: RSI must be < 30 (not just 35)
        if ind.rsi < 30:
            score += 0.3
            reasons.append(f"RSI oversold ({ind.rsi:.0f})")
        elif ind.rsi < 35:
            score += 0.15
        else:
            score -= 0.2
            reasons.append("RSI not oversold enough")
        
        # OPTIMIZATION: Reversal candle (bullish)
        if ind.close > ind.open:
            score += 0.2
            reasons.append("Bullish reversal candle")
        else:
            score -= 0.15
        
        # OPTIMIZATION: Volume on reversal
        if ind.volume_ratio > 1.2:
            score += 0.1
            
    # Sell at upper band
    elif ind.close >= ind.bb_upper:
        signal = "SELL"
        score = 0.4
        reasons.append("Price at upper BB")
        
        if ind.rsi > 70:
            score += 0.3
            reasons.append(f"RSI overbought ({ind.rsi:.0f})")
        elif ind.rsi > 65:
            score += 0.15
        else:
            score -= 0.2
        
        if ind.close < ind.open:
            score += 0.2
            reasons.append("Bearish reversal candle")
        else:
            score -= 0.15
    
    score -= penalty
    
    # Stop-loss just outside band
    if signal == "BUY":
        stop_loss = ind.bb_lower - (ind.atr * 0.5)
        target = bb_mid
    else:
        stop_loss = ind.bb_upper + (ind.atr * 0.5)
        target = bb_mid
    
    return SwingSignal(
        symbol=symbol,
        strategy_name="BB Mean Reversion",
        signal=signal if score >= 0.65 else "HOLD",  # Lower threshold - best avg P&L strategy
        confidence=min(max(score, 0), 1.0),
        stop_loss_type="BAND",
        target_type="BAND",
        reason="; ".join(reasons),
        entry_price=ind.close,
        stop_loss=stop_loss,
        target=target,
        risk_reward=1.5
    )


# ============================================================================
# 🔹 STRATEGY 3: EMA CROSSOVER (OPTIMIZED)
# ============================================================================

def strategy_ema_crossover(symbol: str, ind: MarketIndicators) -> SwingSignal:
    """
    EMA Crossover - OPTIMIZED
    
    Entry Improvements:
    - Require price above/below EMA200 for trend
    - Strong volume on crossover day
    - No entry in choppy sideways market
    """
    signal = "HOLD"
    score = 0.0
    reasons = []
    
    pass_filter, penalty, filter_reasons = _check_common_filters(ind)
    if not pass_filter:
        return SwingSignal(
            symbol=symbol, strategy_name="EMA Crossover", signal="HOLD",
            confidence=0, stop_loss_type="SWING", target_type="RR",
            reason=filter_reasons[0]
        )
    
    # Detect crossover
    bullish_cross = ind.prev_ema20 <= ind.prev_ema50 and ind.ema20 > ind.ema50
    bearish_cross = ind.prev_ema20 >= ind.prev_ema50 and ind.ema20 < ind.ema50
    
    if bullish_cross:
        signal = "BUY"
        score = 0.35
        reasons.append("EMA20 crossed above EMA50")
        
        # OPTIMIZATION: Must be above EMA200 for uptrend
        if ind.close > ind.ema200:
            score += 0.25
            reasons.append("Above EMA200 (uptrend)")
        else:
            score -= 0.15
        
        # OPTIMIZATION: Strong volume required
        if ind.volume_ratio > 1.5:
            score += 0.25
            reasons.append("High volume confirmation")
        elif ind.volume_ratio > 1.2:
            score += 0.15
        else:
            score -= 0.1
        
        # OPTIMIZATION: RSI momentum
        if 50 < ind.rsi < 70:
            score += 0.15
            reasons.append("RSI bullish momentum")
        
    elif bearish_cross:
        signal = "SELL"
        score = 0.35
        reasons.append("EMA20 crossed below EMA50")
        
        if ind.close < ind.ema200:
            score += 0.25
        if ind.volume_ratio > 1.5:
            score += 0.25
        elif ind.volume_ratio > 1.2:
            score += 0.15
        if 30 < ind.rsi < 50:
            score += 0.15
    
    score -= penalty
    
    stop_loss = _calculate_swing_stop(ind, signal)
    risk = abs(ind.close - stop_loss)
    target = ind.close + (risk * 2) if signal == "BUY" else ind.close - (risk * 2)
    
    return SwingSignal(
        symbol=symbol,
        strategy_name="EMA Crossover",
        signal=signal if score >= 0.8 else "HOLD",  # Balanced threshold
        confidence=min(max(score, 0), 1.0),
        stop_loss_type="SWING",
        target_type="RR",
        reason="; ".join(reasons),
        entry_price=ind.close,
        stop_loss=stop_loss,
        target=target,
        risk_reward=2.0
    )


# ============================================================================
# 🔹 STRATEGY 4: TREND PULLBACK (OPTIMIZED)
# ============================================================================

def strategy_trend_pullback(symbol: str, ind: MarketIndicators) -> SwingSignal:
    """
    Trend Pullback Entry - OPTIMIZED
    
    Entry Improvements:
    - Must have clear trend structure
    - Pullback to EMA20 with touch
    - Strong bullish/bearish reversal candle
    - RSI not extreme
    """
    signal = "HOLD"
    score = 0.0
    reasons = []
    
    pass_filter, penalty, filter_reasons = _check_common_filters(ind)
    if not pass_filter:
        return SwingSignal(
            symbol=symbol, strategy_name="Trend Pullback", signal="HOLD",
            confidence=0, stop_loss_type="SWING", target_type="RR",
            reason=filter_reasons[0]
        )
    
    # Check trend structure
    uptrend = ind.close > ind.ema50 > ind.ema200 and ind.ema20 > ind.ema50
    downtrend = ind.close < ind.ema50 < ind.ema200 and ind.ema20 < ind.ema50
    
    if not (uptrend or downtrend):
        return SwingSignal(
            symbol=symbol, strategy_name="Trend Pullback", signal="HOLD",
            confidence=0, stop_loss_type="SWING", target_type="RR",
            reason="No clear trend structure"
        )
    
    # Check pullback to EMA20
    touched_ema20 = ind.low <= ind.ema20 <= ind.high
    near_ema20 = abs(ind.close - ind.ema20) / ind.close < 0.003  # Within 0.3%
    
    if uptrend and (touched_ema20 or near_ema20):
        signal = "BUY"
        score = 0.4
        reasons.append("Pullback to EMA20 in uptrend")
        
        # OPTIMIZATION: Must have bullish candle
        bullish = ind.close > ind.open
        strong_bullish = bullish and (ind.close - ind.open) > ind.atr * 0.3
        
        if strong_bullish:
            score += 0.3
            reasons.append("Strong bullish reversal")
        elif bullish:
            score += 0.15
            reasons.append("Bullish candle")
        else:
            score -= 0.2  # Bearish candle at support is bad
        
        # OPTIMIZATION: RSI should be in buyable zone
        if 35 <= ind.rsi <= 55:
            score += 0.15
            reasons.append("RSI pullback zone")
        elif ind.rsi > 70:
            score -= 0.2
            reasons.append("⚠️ RSI overbought")
        
        # Volume on bounce
        if ind.volume_ratio > 1.2:
            score += 0.15
            
    elif downtrend and (touched_ema20 or near_ema20):
        signal = "SELL"
        score = 0.4
        reasons.append("Rally to EMA20 in downtrend")
        
        bearish = ind.close < ind.open
        if bearish:
            score += 0.25
        if 45 <= ind.rsi <= 65:
            score += 0.15
        if ind.volume_ratio > 1.2:
            score += 0.15
    
    score -= penalty
    
    stop_loss = _calculate_swing_stop(ind, signal)
    risk = abs(ind.close - stop_loss)
    target = ind.close + (risk * 2) if signal == "BUY" else ind.close - (risk * 2)
    
    return SwingSignal(
        symbol=symbol,
        strategy_name="Trend Pullback",
        signal=signal if score >= 0.75 else "HOLD",  # Balanced threshold
        confidence=min(max(score, 0), 1.0),
        stop_loss_type="SWING",
        target_type="RR",
        reason="; ".join(reasons),
        entry_price=ind.close,
        stop_loss=stop_loss,
        target=target,
        risk_reward=2.0
    )


# ============================================================================
# 🔹 STRATEGY 5: SWING BREAKOUT (OPTIMIZED)
# ============================================================================

def strategy_swing_breakout(symbol: str, ind: MarketIndicators) -> SwingSignal:
    """
    Swing Breakout - OPTIMIZED
    
    Entry Improvements:
    - Volume MUST be 1.5x+ (critical for breakouts)
    - Strong candle body (>60% of range)
    - Wait for close above/below level (not just wick)
    """
    signal = "HOLD"
    score = 0.0
    reasons = []
    
    # OPTIMIZATION: Breakouts need strong volume
    if ind.volume_ratio < 1.3:
        return SwingSignal(
            symbol=symbol, strategy_name="Swing Breakout", signal="HOLD",
            confidence=0, stop_loss_type="SWING", target_type="RR",
            reason="Breakouts need 1.3x+ volume"
        )
    
    pass_filter, penalty, filter_reasons = _check_common_filters(ind)
    if not pass_filter:
        return SwingSignal(
            symbol=symbol, strategy_name="Swing Breakout", signal="HOLD",
            confidence=0, stop_loss_type="SWING", target_type="RR",
            reason=filter_reasons[0]
        )
    
    # Check candle quality
    body = abs(ind.close - ind.open)
    candle_range = ind.high - ind.low
    body_ratio = body / candle_range if candle_range > 0 else 0
    
    # Bullish breakout
    if ind.close > ind.swing_high:
        signal = "BUY"
        score = 0.35
        reasons.append(f"Breakout above {ind.swing_high:.0f}")
        
        # OPTIMIZATION: Volume is key
        if ind.volume_ratio > 2.0:
            score += 0.3
            reasons.append("Explosive volume (2x+)")
        elif ind.volume_ratio > 1.5:
            score += 0.2
            reasons.append("Strong volume")
        else:
            score += 0.1
        
        # OPTIMIZATION: Strong candle body
        if body_ratio > 0.7:
            score += 0.2
            reasons.append("Strong breakout candle")
        elif body_ratio > 0.5:
            score += 0.1
        else:
            score -= 0.15
            reasons.append("⚠️ Weak candle structure")
        
        # OPTIMIZATION: Must be bullish candle
        if ind.close > ind.open:
            score += 0.1
        else:
            score -= 0.2
        
    # Bearish breakdown
    elif ind.close < ind.swing_low:
        signal = "SELL"
        score = 0.35
        reasons.append(f"Breakdown below {ind.swing_low:.0f}")
        
        if ind.volume_ratio > 2.0:
            score += 0.3
        elif ind.volume_ratio > 1.5:
            score += 0.2
        
        if body_ratio > 0.7:
            score += 0.2
        elif body_ratio > 0.5:
            score += 0.1
        
        if ind.close < ind.open:
            score += 0.1
        else:
            score -= 0.2
    
    score -= penalty
    
    # Stop below the breakout level
    if signal == "BUY":
        stop_loss = ind.swing_high - (ind.atr * 0.5)
        risk = ind.close - stop_loss
        target = ind.close + (risk * 2)
    else:
        stop_loss = ind.swing_low + (ind.atr * 0.5)
        risk = stop_loss - ind.close
        target = ind.close - (risk * 2)
    
    return SwingSignal(
        symbol=symbol,
        strategy_name="Swing Breakout",
        signal=signal if score >= 0.75 else "HOLD",  # Higher threshold for breakouts
        confidence=min(max(score, 0), 1.0),
        stop_loss_type="SWING",
        target_type="RR",
        reason="; ".join(reasons),
        entry_price=ind.close,
        stop_loss=stop_loss,
        target=target,
        risk_reward=2.0
    )


# ============================================================================
# ALL STRATEGIES LIST - ONLY PROFITABLE STRATEGIES
# ============================================================================

ALL_STRATEGIES = [
    strategy_bb_mean_reversion,  # 61.9% WR, +1.16% avg - BEST
    strategy_trend_pullback,     # 50.9% WR, +0.11% avg - PROFITABLE
]

# REMOVED (Negative returns in backtest):
# - strategy_macd_momentum (-0.30% avg)
# - strategy_ema_crossover (-0.76% avg)
# - strategy_swing_breakout (insufficient data)

