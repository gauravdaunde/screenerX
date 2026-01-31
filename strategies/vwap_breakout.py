#!/usr/bin/env python3
"""
VWAP Breakout Trading Strategy.

This strategy identifies breakout opportunities when price crosses above/below
the Volume Weighted Average Price (VWAP) with EMA confirmation.

Strategy Logic:
    - BUY Signal: Price crosses ABOVE VWAP AND closes above EMA
    - SELL Signal: Price crosses BELOW VWAP AND closes below EMA
    - Stop-Loss: 1.5x ATR below/above entry
    - Take-Profit: Risk:Reward ratio (default 2.0)

Optimal Parameters (from backtesting):
    - VWAP Period: 10
    - EMA Period: 13
    - Risk:Reward Ratio: 2.0

Best Timeframes:
    - Daily (1d) - Primary
    - Hourly (1h) - Secondary

Author: Trading Strategy Screener
Version: 1.0.0
"""

from typing import List, Dict, Any, Optional
import pandas as pd
import numpy as np

from strategies.base import BaseStrategy


class VWAPStrategy(BaseStrategy):
    """
    VWAP Breakout Strategy with EMA Confirmation.
    
    This strategy combines Volume Weighted Average Price (VWAP) with
    Exponential Moving Average (EMA) to identify high-probability
    breakout trades.
    
    Attributes:
        vwap_period: Lookback period for VWAP calculation
        ema_period: Period for EMA calculation
        rr_ratio: Risk to Reward ratio for take-profit
    
    Example:
        >>> strategy = VWAPStrategy(vwap_period=10, ema_period=13, rr_ratio=2.0)
        >>> signals = strategy.check_signals(df)
        >>> for signal in signals:
        ...     print(f"{signal['action']} at {signal['price']}")
    """
    
    def __init__(self, vwap_period: int = 10, ema_period: int = 13, 
                 rr_ratio: float = 2.0):
        """
        Initialize VWAP Strategy with parameters.
        
        Args:
            vwap_period: Lookback period for VWAP calculation (default: 10)
            ema_period: Period for EMA calculation (default: 13)
            rr_ratio: Risk to Reward ratio for take-profit (default: 2.0)
        """
        self.vwap_period = vwap_period
        self.ema_period = ema_period
        self.rr_ratio = rr_ratio
    
    def name(self) -> str:
        """
        Get strategy name.
        
        Returns:
            Short identifier string for the strategy
        """
        return f"VWAP_V{self.vwap_period}_E{self.ema_period}"
    
    def description(self) -> str:
        """
        Get strategy description.
        
        Returns:
            Human-readable description of the strategy
        """
        return f"VWAP({self.vwap_period}) + EMA({self.ema_period}) Breakout"
    
    def _calculate_vwap(self, df: pd.DataFrame) -> pd.Series:
        """
        Calculate Volume Weighted Average Price.
        
        VWAP = Cumulative(Typical Price × Volume) / Cumulative(Volume)
        where Typical Price = (High + Low + Close) / 3
        
        Args:
            df: DataFrame with high, low, close, volume columns
            
        Returns:
            Series containing VWAP values
        """
        typical_price = (df['high'] + df['low'] + df['close']) / 3
        tp_vol = typical_price * df['volume']
        
        return (
            tp_vol.rolling(self.vwap_period).sum() / 
            df['volume'].rolling(self.vwap_period).sum()
        )
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """
        Calculate Average True Range for volatility-based stops.
        
        ATR = SMA(True Range, period)
        where True Range = max(H-L, |H-Prev Close|, |L-Prev Close|)
        
        Args:
            df: DataFrame with high, low, close columns
            period: Lookback period for ATR (default: 14)
            
        Returns:
            Series containing ATR values
        """
        tr = np.maximum(
            df['high'] - df['low'],
            np.maximum(
                abs(df['high'] - df['close'].shift(1)),
                abs(df['low'] - df['close'].shift(1))
            )
        )
        return tr.rolling(period).mean()
    
    def check_signals(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Scan DataFrame for buy/sell signals.
        
        Args:
            df: DataFrame with OHLCV data (columns: open, high, low, close, volume)
            
        Returns:
            List of signal dictionaries, each containing:
                - action: 'BUY' or 'SELL'
                - price: Entry price
                - sl: Stop-loss price
                - tp: Take-profit price
                - time: Signal timestamp
                - reason: Signal description
        """
        signals: List[Dict[str, Any]] = []
        
        if len(df) < 30:
            return signals
        
        # Ensure lowercase columns
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]
        
        # Calculate indicators
        df['vwap'] = self._calculate_vwap(df)
        df['ema'] = df['close'].ewm(span=self.ema_period, adjust=False).mean()
        df['atr'] = self._calculate_atr(df)
        
        # Previous values for crossover detection
        df['prev_close'] = df['close'].shift(1)
        df['prev_vwap'] = df['vwap'].shift(1)
        
        # Scan for signals
        for i in range(25, len(df)):
            close = df['close'].iloc[i]
            prev_close = df['prev_close'].iloc[i]
            vwap = df['vwap'].iloc[i]
            prev_vwap = df['prev_vwap'].iloc[i]
            ema = df['ema'].iloc[i]
            atr = df['atr'].iloc[i]
            time = df.index[i]
            
            # Skip if any indicator is NaN
            if pd.isna(vwap) or pd.isna(ema) or pd.isna(atr):
                continue
            
            # BUY: Cross above VWAP + Close > EMA
            cross_above_vwap = (prev_close <= prev_vwap) and (close > vwap)
            above_ema = close > ema
            
            if cross_above_vwap and above_ema:
                sl = close - (atr * 1.5)
                risk = close - sl
                tp = close + (risk * self.rr_ratio)
                
                signals.append({
                    'action': 'BUY',
                    'price': close,
                    'sl': sl,
                    'tp': tp,
                    'time': time,
                    'reason': f"VWAP Long: Cross above VWAP {vwap:.2f}, EMA {ema:.2f}"
                })
            
            # SELL: Cross below VWAP + Close < EMA
            cross_below_vwap = (prev_close >= prev_vwap) and (close < vwap)
            below_ema = close < ema
            
            if cross_below_vwap and below_ema:
                sl = close + (atr * 1.5)
                risk = sl - close
                tp = close - (risk * self.rr_ratio)
                
                signals.append({
                    'action': 'SELL',
                    'price': close,
                    'sl': sl,
                    'tp': tp,
                    'time': time,
                    'reason': f"VWAP Short: Cross below VWAP {vwap:.2f}, EMA {ema:.2f}"
                })
        
        return signals
