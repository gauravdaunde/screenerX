
"""
NIFTY 5m Scalping Strategy (Dual Jackpot Mode) - DhanHQ Version

This module implements two variations of a Trend-Following Scalping Strategy:
1. Jackpot Strict Strategy (High Accuracy)
2. Jackpot Normal Strategy (High Profit Potential)

Both strategies target a Risk:Reward of 1:3 and are designed to capture 
large trend movements ("Jackpots") on the 5-minute timeframe.

LLM Friendly Strategy Overview:
------------------------------
- Core Trend: EMA 20, 50, 200 alignment.
- Entry: Pullback to EMA 20.
- Risk Management: 1:3 Risk:Reward using ATR-based stops.
- Modes: 'Strict' for sniper entries, 'Normal' for trend participation.
"""

import pandas as pd
import numpy as np
import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime, timedelta

@dataclass
class ScalpSignal:
    timestamp: str
    symbol: str
    action: str # ENTER_LONG, ENTER_SHORT, WAIT
    strategy_name: str
    entry_price: float
    stop_loss: float
    target: float
    confidence: int
    reasons: List[str]

# =============================================================================
# STRATEGY 1: JACKPOT STRICT (High Accuracy Sniper)
# =============================================================================
class JackpotStrictStrategy:
    """
    Implements the 'Strict' Jackpot Strategy. High probability, lower frequency.
    
    Strategy Logic for LLM Reasoning:
    ---------------------------------
    1. **Trend Check**: Requires perfect alignment (Close > EMA20 > EMA50 > EMA200).
    2. **Momentum Check**: ADX > 20 ensures we aren't in a sideways market.
    3. **RSI Requirement**: 
       - Long: RSI [60, 75] ensures strong bullish conviction without being over-extended.
       - Short: RSI [25, 40] ensures strong bearish conviction.
    4. **Trigger**: Pullback within 0.15% of EMA 20. Must be a price-action confirmation candle 
       (Green for Long, Red for Short).

    Execution Parameters:
    ---------------------
    - Risk:Reward: 1:3.
    - Stop Loss: 1.0 * ATR offset from the signal candle extremes.
    """
    
    def __init__(self, risk_reward=3.0, atr_mult=1.0):
        self.risk_reward = risk_reward
        self.atr_mult = atr_mult

    def check_signal(self, candle: pd.Series) -> Optional[Dict]:
        """
        Analyzes a candle for 'Strict' entry criteria.
        
        Args:
            candle (pd.Series): Row containing OHLC, EMA_20, EMA_50, EMA_200, RSI, ADX, ATR.
            
        Returns:
            Optional[Dict]: Signal details if criteria met, else None.
        """
        close = candle['close']
        open_p = candle['open']
        high = candle['high']
        low = candle['low']
        
        ema20 = candle['ema_20']
        ema50 = candle['ema_50']
        ema200 = candle['ema_200']
        rsi = candle['rsi']
        adx = candle['adx']
        entr_atr = candle['atr']

        # BULLISH STRICT
        if close > ema200 and close > ema50 and close > ema20:
             dist = (close - ema20) / close
             # Logic: Near EMA20, Green Candle, High RSI Momentum
             if dist < 0.0015 and close > open_p:
                 if adx > 20 and 60 <= rsi <= 75:
                     sl = low - (entr_atr * self.atr_mult)
                     risk = close - sl
                     if risk < 10: risk = 10 # Min point floor
                     tp = close + (risk * self.risk_reward)
                     
                     return {
                         "action": "ENTER_LONG",
                         "sl": sl,
                         "tp": tp,
                         "confidence": 95,
                         "reason": "Strict Bullish: Perfect Trend + High RSI Momentum"
                     }

        # BEARISH STRICT
        elif close < ema200 and close < ema50 and close < ema20:
             dist = (ema20 - close) / close
             # Logic: Near EMA20, Red Candle, Low RSI Momentum
             if dist < 0.0015 and close < open_p:
                 if adx > 20 and 25 <= rsi <= 40:
                     sl = high + (entr_atr * self.atr_mult)
                     risk = sl - close
                     if risk < 10: risk = 10
                     tp = close - (risk * self.risk_reward)
                     
                     return {
                         "action": "ENTER_SHORT",
                         "sl": sl,
                         "tp": tp,
                         "confidence": 95,
                         "reason": "Strict Bearish: Perfect Trend + High RSI Weakness"
                     }
        return None

# =============================================================================
# STRATEGY 2: JACKPOT NORMAL (Trend Participation)
# =============================================================================
class JackpotNormalStrategy:
    """
    Implements the 'Normal' Jackpot Strategy. Higher frequency, captures trend continuation.
    
    Strategy Logic for LLM Reasoning:
    ---------------------------------
    1. **Trend Check**: Basic alignment (Close > EMA20 > EMA50 > EMA200).
    2. **Momentum Check**: ADX > 20.
    3. **RSI Requirement**: 
       - Long: RSI > 50 (Standard Bullishness).
       - Short: RSI < 50 (Standard Bearishness).
    4. **Trigger**: Pullback within 0.15% of EMA 20.

    Execution Parameters:
    ---------------------
    - Risk:Reward: 1:3.
    """
    
    def __init__(self, risk_reward=3.0, atr_mult=1.0):
        self.risk_reward = risk_reward
        self.atr_mult = atr_mult

    def check_signal(self, candle: pd.Series) -> Optional[Dict]:
        """
        Analyzes a candle for 'Normal' entry criteria.
        """
        close = candle['close']
        open_p = candle['open']
        high = candle['high']
        low = candle['low']
        
        ema20 = candle['ema_20']
        ema50 = candle['ema_50']
        ema200 = candle['ema_200']
        rsi = candle['rsi']
        adx = candle['adx']
        entr_atr = candle['atr']

        # BULLISH NORMAL
        if close > ema200 and close > ema50 and close > ema20:
             dist = (close - ema20) / close
             if dist < 0.0015 and close > open_p:
                 if adx > 20 and 50 <= rsi <= 75:
                     sl = low - (entr_atr * self.atr_mult)
                     risk = close - sl
                     if risk < 10: risk = 10
                     tp = close + (risk * self.risk_reward)
                     
                     return {
                         "action": "ENTER_LONG",
                         "sl": sl,
                         "tp": tp,
                         "confidence": 75,
                         "reason": "Normal Bullish: Standard RSI Breakout"
                     }

        # BEARISH NORMAL
        elif close < ema200 and close < ema50 and close < ema20:
             dist = (ema20 - close) / close
             if dist < 0.0015 and close < open_p:
                 if adx > 20 and 25 <= rsi <= 50:
                     sl = high + (entr_atr * self.atr_mult)
                     risk = sl - close
                     if risk < 10: risk = 10
                     tp = close - (risk * self.risk_reward)
                     
                     return {
                         "action": "ENTER_SHORT",
                         "sl": sl,
                         "tp": tp,
                         "confidence": 75,
                         "reason": "Normal Bearish: Standard RSI Breakout"
                     }
        return None

# =============================================================================
# MAIN SCANNER CLASS
# =============================================================================
class NiftyScalper:
    """
    Orchestrator class for NIFTY 5m Dual Jackpot Strategy.
    Fetches data, calculates indicators, and evaluates multiple strategies.
    """
    def __init__(self, symbol="NIFTY"):
        self.symbol = symbol
        self.security_id = "13" # NIFTY 50 Index
        self.exchange_segment = "IDX_I"
        self.instrument_type = "INDEX"
        
        # Strategies
        self.strategies = [
            JackpotStrictStrategy(risk_reward=3.0),
            JackpotNormalStrategy(risk_reward=3.0)
        ]
        
        # Init Dhan
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
        try:
            from app.core.dhan_client import get_dhan_client
            self.dhan = get_dhan_client()
        except ImportError:
            self.dhan = None
        
    def fetch_data(self) -> pd.DataFrame:
        """Fetches latest 5-min OHLC data from Dhan API."""
        if not self.dhan: return pd.DataFrame()
        try:
            to_date = datetime.now().strftime('%Y-%m-%d')
            # 5 days window ensures stable indicator calculation (EMA 200)
            from_date = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
            
            res = self.dhan.intraday_minute_data(
                security_id=self.security_id, exchange_segment=self.exchange_segment,
                instrument_type=self.instrument_type, from_date=from_date, to_date=to_date, interval=5
            )
            
            if res.get('status') != 'success' or not res.get('data'): return pd.DataFrame()
            df = pd.DataFrame(res['data'])
            
            # Standardize Timestamp
            for col in ['start_Time', 'timestamp', 'k']:
                if col in df.columns:
                    df['datetime'] = pd.to_datetime(df[col], unit='s')
                    break
            else: return pd.DataFrame()
                 
            df = df.set_index('datetime').sort_index()
            df = df.rename(columns={'o':'open','h':'high','l':'low','c':'close','v':'volume'})
            
            # Return cleaned OHLC
            expected = ['open','high','low','close']
            return df[expected].astype(float)
        except Exception:
            return pd.DataFrame()

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculates indicators used by the strategies."""
        if df.empty: return df
        # EMAs
        for s in [20, 50, 200]: 
            df[f'ema_{s}'] = df['close'].ewm(span=s, adjust=False).mean()
        # RSI 14
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        # ATR 14
        df['tr'] = np.maximum(df['high'] - df['low'], 
                              np.maximum(abs(df['high'] - df['close'].shift(1)), 
                                         abs(df['low'] - df['close'].shift(1))))
        df['atr'] = df['tr'].rolling(14).mean()
        # ADX 14
        df['up_move'] = df['high'] - df['high'].shift(1)
        df['down_move'] = df['low'].shift(1) - df['low']
        df['plus_dm'] = np.where((df['up_move'] > df['down_move']) & (df['up_move'] > 0), df['up_move'], 0)
        df['minus_dm'] = np.where((df['down_move'] > df['up_move']) & (df['down_move'] > 0), df['down_move'], 0)
        df['plus_di'] = 100 * (df['plus_dm'].ewm(span=14).mean() / df['atr'])
        df['minus_di'] = 100 * (df['minus_dm'].ewm(span=14).mean() / df['atr'])
        df['dx'] = 100 * abs(df['plus_di'] - df['minus_di']) / (df['plus_di'] + df['minus_di'])
        df['adx'] = df['dx'].ewm(span=14).mean()
        return df

    def scan(self) -> ScalpSignal:
        """Runs the scanning logic and returns the best signal found."""
        df = self.fetch_data()
        if df.empty or len(df) < 200:
             return ScalpSignal(datetime.now().isoformat(), self.symbol, "WAIT", "NONE", 0, 0, 0, 0, ["Insufficient Historical Data"])
            
        df = self.calculate_indicators(df)
        last_candle = df.iloc[-1]
        
        if pd.isna(last_candle['adx']):
             return ScalpSignal(datetime.now().isoformat(), self.symbol, "WAIT", "NONE", 0, 0, 0, 0, ["Indicators Warming Up"])

        # Check strategies in order of priority (Strict first)
        for strategy in self.strategies:
            res = strategy.check_signal(last_candle)
            if res:
                s_name = strategy.__class__.__name__.replace("Strategy", "").upper()
                return ScalpSignal(
                    timestamp=datetime.now().isoformat(),
                    symbol=self.symbol,
                    action=res['action'],
                    strategy_name=f"JACKPOT_{s_name}",
                    entry_price=round(last_candle['close'], 2),
                    stop_loss=round(res['sl'], 2),
                    target=round(res['tp'], 2),
                    confidence=res['confidence'],
                    reasons=[res['reason']]
                )
            
        return ScalpSignal(
            datetime.now().isoformat(), self.symbol, "WAIT", "NONE", 0, 0, 0, 0, ["No valid trade setups found"]
        )

if __name__ == "__main__":
    scalper = NiftyScalper()
    sig = scalper.scan()
    print(sig)
