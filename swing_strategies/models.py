"""
Swing Trading Strategies - Data Models

Defines the standard signal format and indicator structure.
"""

from dataclasses import dataclass
from typing import Literal, Dict, Optional
import pandas as pd


@dataclass
class SwingSignal:
    """Standard output format for swing trading signals."""
    symbol: str
    strategy_name: str
    signal: Literal["BUY", "SELL", "HOLD"]
    confidence: float  # 0.0 to 1.0
    stop_loss_type: Literal["ATR", "SWING", "PERCENT"]
    target_type: Literal["RR", "RESISTANCE", "BAND"]
    holding_type: str = "SWING"
    reason: str = ""
    
    # Optional trade parameters
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    target: Optional[float] = None
    risk_reward: Optional[float] = None
    
    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "strategy_name": self.strategy_name,
            "signal": self.signal,
            "confidence": round(self.confidence, 2),
            "stop_loss_type": self.stop_loss_type,
            "target_type": self.target_type,
            "holding_type": self.holding_type,
            "reason": self.reason,
            "entry_price": self.entry_price,
            "stop_loss": self.stop_loss,
            "target": self.target,
            "risk_reward": self.risk_reward
        }


@dataclass
class MarketIndicators:
    """All technical indicators needed for swing strategies."""
    # Price
    close: float
    high: float
    low: float
    open: float
    
    # EMAs
    ema20: float
    ema50: float
    ema200: float
    
    # Momentum
    rsi: float
    macd: float
    macd_signal: float
    macd_histogram: float
    
    # Volatility
    atr: float
    bb_upper: float
    bb_lower: float
    bb_width: float
    
    # Volume
    volume: float
    volume_avg: float
    volume_ratio: float
    
    # Structure
    swing_high: float
    swing_low: float
    trend: Literal["UP", "DOWN", "SIDEWAYS"]
    
    # Previous values for crossover detection
    prev_ema20: float = 0
    prev_ema50: float = 0
    prev_macd: float = 0
    prev_macd_signal: float = 0
    prev_rsi: float = 50
