
"""
NIFTY 5m Scalping Strategy (Pullback) - DhanHQ Version
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
    entry_price: float
    stop_loss: float
    target: float
    confidence: int
    reasons: List[str]

class NiftyScalper:
    def __init__(self, symbol="NIFTY"):
        self.symbol = symbol
        self.security_id = "13" # NIFTY 50 Index
        self.exchange_segment = "IDX_I"
        self.instrument_type = "INDEX"
        
        self.ema_fast = 20
        self.ema_slow = 50
        self.ema_trend = 200
        self.risk_reward = 1.5
        
        # Init Dhan
        # Add project root to path
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
        from app.core.dhan_client import get_dhan_client
        self.dhan = get_dhan_client()
        
    def fetch_data(self) -> pd.DataFrame:
        if not self.dhan:
            return pd.DataFrame()
            
        try:
            to_date = datetime.now().strftime('%Y-%m-%d')
            # Fetch 5 days
            from_date = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
            
            res = self.dhan.intraday_minute_data(
                security_id=self.security_id,
                exchange_segment=self.exchange_segment,
                instrument_type=self.instrument_type,
                from_date=from_date,
                to_date=to_date,
                interval=5
            )
            
            if res.get('status') != 'success' or not res.get('data'):
                return pd.DataFrame()
                
            df = pd.DataFrame(res['data'])
            
            # Handle potential column names
            if 'start_Time' in df.columns:
                 df['datetime'] = pd.to_datetime(df['start_Time'], unit='s')
            elif 'timestamp' in df.columns:
                 df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
            elif 'k' in df.columns:
                 df['datetime'] = pd.to_datetime(df['k'], unit='s')
            else:
                 print(f"Unknown columns: {df.columns}")
                 return pd.DataFrame() # Fail gracefully
                 
            df = df.set_index('datetime')
            
            rename = {'o':'open','h':'high','l':'low','c':'close','v':'volume'}
            df = df.rename(columns=rename)
            
            # Clean up columns if needed
            req_cols = ['open','high','low','close']
            for c in req_cols:
                if c not in df.columns:
                    # Fallback to original names if rename failed (e.g. key missing)
                    pass
            
            df = df[['open','high','low','close']].astype(float)
            
            return df
            
        except Exception as e:
            print(f"Fetch Error: {e}")
            return pd.DataFrame()

    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
            
        # EMAs
        df['ema_20'] = df['close'].ewm(span=self.ema_fast, adjust=False).mean()
        df['ema_50'] = df['close'].ewm(span=self.ema_slow, adjust=False).mean()
        df['ema_200'] = df['close'].ewm(span=self.ema_trend, adjust=False).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['rsi'] = 100 - (100 / (1 + rs))
        
        # ATR
        df['tr'] = np.maximum(df['high'] - df['low'], 
                              np.maximum(abs(df['high'] - df['close'].shift(1)), 
                                         abs(df['low'] - df['close'].shift(1))))
        df['atr'] = df['tr'].rolling(14).mean()
        
        # ADX
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
        df = self.fetch_data()
        if df.empty:
            return ScalpSignal(datetime.now().isoformat(), self.symbol, "WAIT", 0, 0, 0, 0, ["No Data (Dhan)"])
            
        df = self.calculate_indicators(df)
        
        last_candle = df.iloc[-1]
        
        close = last_candle['close']
        high = last_candle['high']
        low = last_candle['low']
        open_p = last_candle['open']
        
        ema20 = last_candle['ema_20']
        ema50 = last_candle['ema_50']
        ema200 = last_candle['ema_200']
        rsi = last_candle['rsi']
        adx = last_candle['adx']
        atr = last_candle['atr']
        
        if pd.isna(atr) or pd.isna(adx):
             return ScalpSignal(datetime.now().isoformat(), self.symbol, "WAIT", 0, 0, 0, 0, ["Indicators warming up"])

        # LONG Logic
        is_uptrend = close > ema20 and ema20 > ema50 and ema50 > ema200
        touched_zone_long = low <= (ema20 * 1.0005) and close > ema20
        is_green = close > open_p
        rsi_long_ok = 40 <= rsi <= 65
        adx_ok = adx > 20
        
        if is_uptrend and touched_zone_long and is_green and rsi_long_ok and adx_ok:
            entry = high + 1
            stop = low - (atr * 1.5)
            risk = entry - stop
            target = entry + (risk * self.risk_reward)
            
            return ScalpSignal(
                timestamp=datetime.now().isoformat(),
                symbol=self.symbol,
                action="ENTER_LONG",
                entry_price=round(entry, 2),
                stop_loss=round(stop, 2),
                target=round(target, 2),
                confidence=85 if adx > 25 else 75,
                reasons=[
                    "Strong Uptrend (Price > 20 > 50 > 200)",
                    "Pullback to EMA20",
                    f"ADX {adx:.1f} > 20",
                    f"RSI {rsi:.1f} Bullish"
                ]
            )

        # SHORT Logic
        is_downtrend = close < ema20 and ema20 < ema50 and ema50 < ema200
        touched_zone_short = high >= (ema20 * 0.9995) and close < ema20
        is_red = close < open_p
        rsi_short_ok = 35 <= rsi <= 60
        
        if is_downtrend and touched_zone_short and is_green and rsi_short_ok and adx_ok:
            entry = low - 1
            stop = high + (atr * 1.5)
            risk = stop - entry
            target = entry - (risk * self.risk_reward)
            
            return ScalpSignal(
                timestamp=datetime.now().isoformat(),
                symbol=self.symbol,
                action="ENTER_SHORT",
                entry_price=round(entry, 2),
                stop_loss=round(stop, 2),
                target=round(target, 2),
                confidence=85 if adx > 25 else 75,
                reasons=[
                    "Strong Downtrend (Price < 20 < 50 < 200)",
                    "Pullback to EMA20",
                    f"ADX {adx:.1f} > 20",
                    f"RSI {rsi:.1f} Bearish"
                ]
            )
            
        return ScalpSignal(
            timestamp=datetime.now().isoformat(),
            symbol=self.symbol,
            action="WAIT",
            entry_price=0,
            stop_loss=0,
            target=0,
            confidence=0,
            reasons=["No setup found"]
        )

if __name__ == "__main__":
    scalper = NiftyScalper()
    sig = scalper.scan()
    print(sig)
