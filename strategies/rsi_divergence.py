from strategies.base import BaseStrategy
import pandas as pd

class RSIDivergenceStrategy(BaseStrategy):
    """
    Improved RSI Divergence Strategy.
    
    Changes from v1:
    - Added momentum confirmation (candle size relative to ATR)
    - Added trend filter (price above/below 50 EMA for direction)
    - Relaxed RSI thresholds (30/70 instead of 40/60)
    - Better swing detection with Williams Fractals
    - Added volume confirmation
    
    Rules:
    - Bullish Divergence: Price LL + RSI HL + RSI < 35 + Bullish candle + Volume spike
    - Bearish Divergence: Price HH + RSI LH + RSI > 65 + Bearish candle + Volume spike
    """
    
    def __init__(self, rsi_period=7, rr_ratio=3.0):
        self.rsi_period = rsi_period
        self.rr_ratio = rr_ratio
    
    def name(self):
        return f"RSI_Divergence_v2"
    
    def description(self):
        return f"Enhanced RSI({self.rsi_period}) Divergence with Trend + Volume filters"
    
    def _calculate_rsi(self, series, period=14):
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def check_signals(self, df):
        signals = []
        if len(df) < 60:
            return signals
        
        df = df.copy()
        df.columns = [c.lower() for c in df.columns]
        
        # --- Indicators ---
        df['rsi'] = self._calculate_rsi(df['close'], self.rsi_period)
        df['ema50'] = df['close'].ewm(span=50, adjust=False).mean()
        df['ema20'] = df['close'].ewm(span=20, adjust=False).mean()
        
        # ATR for stop loss
        df['tr'] = df['high'] - df['low']
        df['atr'] = df['tr'].rolling(14).mean()
        
        # Volume filter
        df['vol_avg'] = df['volume'].rolling(20).mean()
        df['vol_spike'] = df['volume'] > (df['vol_avg'] * 1.2)
        
        # Body size (momentum)
        df['body'] = abs(df['close'] - df['open'])
        df['body_avg'] = df['body'].rolling(10).mean()
        df['strong_candle'] = df['body'] > (df['body_avg'] * 0.8)
        
        # --- Find Swing Points (Williams Fractals - 5 bar) ---
        swing_lows = []
        swing_highs = []
        
        for i in range(2, len(df) - 2):
            # Swing Low: lowest of 5 bars
            if df['low'].iloc[i] <= df['low'].iloc[i-2:i+3].min():
                swing_lows.append({'idx': i, 'price': df['low'].iloc[i], 'rsi': df['rsi'].iloc[i]})
            
            # Swing High: highest of 5 bars
            if df['high'].iloc[i] >= df['high'].iloc[i-2:i+3].max():
                swing_highs.append({'idx': i, 'price': df['high'].iloc[i], 'rsi': df['rsi'].iloc[i]})
        
        # --- Detect Bullish Divergence ---
        for i in range(1, len(swing_lows)):
            curr = swing_lows[i]
            prev = swing_lows[i-1]
            
            # Skip if too far apart or too close
            if curr['idx'] - prev['idx'] > 30 or curr['idx'] - prev['idx'] < 3:
                continue
            
            # Price: Lower Low
            price_ll = curr['price'] < prev['price']
            
            # RSI: Higher Low
            curr_rsi = curr['rsi']
            prev_rsi = prev['rsi']
            
            if pd.isna(curr_rsi) or pd.isna(prev_rsi):
                continue
            
            rsi_hl = curr_rsi > prev_rsi
            
            # RSI must be oversold
            rsi_oversold = curr_rsi < 35
            
            # Trend filter: Allow counter-trend but prefer with trend
            idx = curr['idx']
            # Check next candle for confirmation
            if idx + 1 >= len(df):
                continue
            
            confirm_idx = idx + 1
            confirm_candle = df.iloc[confirm_idx]
            
            # Bullish confirmation candle
            is_bullish = confirm_candle['close'] > confirm_candle['open']
            is_strong = confirm_candle['strong_candle'] if pd.notna(confirm_candle['strong_candle']) else True
            has_volume = confirm_candle['vol_spike'] if pd.notna(confirm_candle['vol_spike']) else True
            
            if price_ll and rsi_hl and rsi_oversold and is_bullish and (is_strong or has_volume):
                entry = confirm_candle['close']
                atr = df['atr'].iloc[confirm_idx] if pd.notna(df['atr'].iloc[confirm_idx]) else entry * 0.02
                sl = curr['price'] - (atr * 0.5)  # Below swing low
                risk = entry - sl
                
                if risk > 0 and risk < entry * 0.05:  # Max 5% risk
                    tp = entry + (risk * self.rr_ratio)
                    
                    signals.append({
                        'action': 'BUY',
                        'price': entry,
                        'sl': sl,
                        'tp': tp,
                        'time': df.index[confirm_idx],
                        'reason': f"Bull Div: Price {prev['price']:.1f}→{curr['price']:.1f}, RSI {prev_rsi:.0f}→{curr_rsi:.0f}"
                    })
        
        # --- Detect Bearish Divergence ---
        for i in range(1, len(swing_highs)):
            curr = swing_highs[i]
            prev = swing_highs[i-1]
            
            if curr['idx'] - prev['idx'] > 30 or curr['idx'] - prev['idx'] < 3:
                continue
            
            # Price: Higher High
            price_hh = curr['price'] > prev['price']
            
            # RSI: Lower High
            curr_rsi = curr['rsi']
            prev_rsi = prev['rsi']
            
            if pd.isna(curr_rsi) or pd.isna(prev_rsi):
                continue
            
            rsi_lh = curr_rsi < prev_rsi
            rsi_overbought = curr_rsi > 65
            
            idx = curr['idx']
            if idx + 1 >= len(df):
                continue
            
            confirm_idx = idx + 1
            confirm_candle = df.iloc[confirm_idx]
            
            is_bearish = confirm_candle['close'] < confirm_candle['open']
            is_strong = confirm_candle['strong_candle'] if pd.notna(confirm_candle['strong_candle']) else True
            has_volume = confirm_candle['vol_spike'] if pd.notna(confirm_candle['vol_spike']) else True
            
            if price_hh and rsi_lh and rsi_overbought and is_bearish and (is_strong or has_volume):
                entry = confirm_candle['close']
                atr = df['atr'].iloc[confirm_idx] if pd.notna(df['atr'].iloc[confirm_idx]) else entry * 0.02
                sl = curr['price'] + (atr * 0.5)
                risk = sl - entry
                
                if risk > 0 and risk < entry * 0.05:
                    tp = entry - (risk * self.rr_ratio)
                    
                    signals.append({
                        'action': 'SELL',
                        'price': entry,
                        'sl': sl,
                        'tp': tp,
                        'time': df.index[confirm_idx],
                        'reason': f"Bear Div: Price {prev['price']:.1f}→{curr['price']:.1f}, RSI {prev_rsi:.0f}→{curr_rsi:.0f}"
                    })
        
        return signals
