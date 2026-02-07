
import logging
import sys
import os
import time
import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
from dhanhq import dhanhq
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from app.core import config

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class NiftyScalperLive:
    """
    Live Scalper for NIFTY using DhanHQ API.
    Uses NIFTY INDEX SPOT Data (ID 13).
    Strategy: 5-min EMA Pullback Trend Following (Jackpot Hunt RR 3.0).
    """
    def __init__(self):
        load_dotenv(".env")
        self.client_id = os.getenv("DHAN_CLIENT_ID")
        self.access_token = os.getenv("DHAN_ACCESS_TOKEN")
        
        try:
            self.dhan = dhanhq(self.client_id, self.access_token)
            self.dhan.base_url = "https://api.dhan.co/v2" # FORCE PROD URL
        except Exception as e:
            logging.error(f"Dhan Init Error: {e}")
            self.dhan = None
        
        # CONFIG: NIFTY SPOT INDEX
        self.security_id = '13' 
        self.exchange_segment = 'IDX_I'
        self.instrument_type = 'INDEX'
        self.symbol = "NIFTY-INDEX"
        self.interval = 5 
        
        # Telegram
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        
        # State
        self.df = None
        self.last_candle_time = None
        self.in_position = False
        
        # Strategy Params
        self.ema_fast = 20
        self.ema_slow = 50
        self.ema_trend = 200
        self.rsi_period = 14
        self.risk_reward = 3.0 # JACKPOT HUNT
        
    def send_telegram(self, message):
        if not self.telegram_token or not self.chat_id:
            logging.warning("Telegram credentials missing.")
            return
        
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        data = {"chat_id": self.chat_id, "text": message, "parse_mode": "Markdown"}
        try:
            requests.post(url, data=data)
        except Exception as e:
            logging.error(f"Telegram Send Error: {e}")

    def fetch_data(self):
        """Fetch ~5 days of data"""
        try:
            to_date = datetime.now().strftime('%Y-%m-%d')
            from_date = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
            
            res = self.dhan.intraday_minute_data(
                security_id=self.security_id,
                exchange_segment=self.exchange_segment,
                instrument_type=self.instrument_type,
                from_date=from_date,
                to_date=to_date,
                interval=self.interval
            )
            
            if res.get('status') == 'failure':
                logging.error(f"Dhan Data Fetch Failed: {res.get('remarks')}")
                return False
                
            data = res.get('data')
            if not data:
                logging.warning("No data returned.")
                return False
                
            df = pd.DataFrame(data)
            
            if 'start_Time' in df.columns:
                 df['datetime'] = pd.to_datetime(df['start_Time'], unit='s')
            elif 'timestamp' in df.columns:
                 df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
            elif 'k' in df.columns:
                 df['datetime'] = pd.to_datetime(df['k'], unit='s')
            else:
                 logging.error(f"Unknown date columns: {df.columns}")
                 return False
            
            df = df.set_index('datetime')
            df.index = pd.to_datetime(df.index)
            # IST Convert for Display/Log logic (optional, but good for logs)
            # df.index = df.index.tz_localize('UTC').tz_convert('Asia/Kolkata') 
            # Dhan returns UTC timestamp usually.
            
            rename = {'o':'open','h':'high','l':'low','c':'close','v':'volume'}
            df = df.rename(columns=rename)
            
            req = ['open','high','low','close']
            df = df[[c for c in req if c in df.columns]].astype(float)
            
            self.df = df
            logging.info(f"Fetched {len(df)} candles.")
            return True
            
        except Exception as e:
            logging.error(f"Fetch Data Error: {e}")
            return False

    def calculate_indicators(self):
        if self.df is None or self.df.empty:
            return

        df = self.df
        
        # EMAs
        df['ema_20'] = df['close'].ewm(span=self.ema_fast, adjust=False).mean()
        df['ema_50'] = df['close'].ewm(span=self.ema_slow, adjust=False).mean()
        df['ema_200'] = df['close'].ewm(span=self.ema_trend, adjust=False).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
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
        
        self.df = df

    def check_signal(self):
        if self.df is None or len(self.df) < 50:
            return
            
        last_row = self.df.iloc[-1]
        last_time = self.df.index[-1]
        
        if self.last_candle_time == last_time:
            return
            
        self.last_candle_time = last_time
        
        close = last_row['close']
        high = last_row['high']
        low = last_row['low']
        open_p = last_row['open']
        ema20 = last_row['ema_20']
        ema50 = last_row['ema_50']
        ema200 = last_row['ema_200']
        rsi = last_row['rsi']
        adx = last_row['adx']
        atr = last_row['atr']
        
        logging.info(f"Analysis at {last_time}: Close={close}, EMA20={ema20:.2f}, RSI={rsi:.2f}")
        
        # LONG Checks
        is_uptrend = close > ema20 and ema20 > ema50 and ema50 > ema200
        touched_zone_long = low <= (ema20 * 1.0005) and close > ema20
        is_green = close > open_p
        rsi_ok_long = 40 <= rsi <= 65
        adx_ok = adx > 20
        
        if is_uptrend and touched_zone_long and is_green and rsi_ok_long and adx_ok:
            trigger_entry = high + 1
            stop_loss = low - (atr * 1.5)
            risk = trigger_entry - stop_loss
            if risk > 0:
                target = trigger_entry + (risk * self.risk_reward)
                msg = (f"🚀 *LONG SIGNAL (Jackpot 3.0)* - {self.symbol}\n"
                       f"Time: {last_time}\n"
                       f"👉 ENTER Above: {trigger_entry:.2f}\n"
                       f"🛑 Stop Loss: {stop_loss:.2f}\n"
                       f"🎯 Target: {target:.2f} (RR 3.0)\n"
                       f"Risk: {risk:.2f} pts")
                print(msg)
                self.send_telegram(msg)
                return

        # SHORT Checks
        is_downtrend = close < ema20 and ema20 < ema50 and ema50 < ema200
        touched_zone_short = high >= (ema20 * 0.9995) and close < ema20
        is_red = close < open_p
        rsi_ok_short = 35 <= rsi <= 60
        
        if is_downtrend and touched_zone_short and is_red and rsi_ok_short and adx_ok:
            trigger_entry = low - 1
            stop_loss = high + (atr * 1.5)
            risk = stop_loss - trigger_entry
            if risk > 0:
                target = trigger_entry - (risk * self.risk_reward)
                msg = (f"🔻 *SHORT SIGNAL (Jackpot 3.0)* - {self.symbol}\n"
                       f"Time: {last_time}\n"
                       f"👉 ENTER Below: {trigger_entry:.2f}\n"
                       f"🛑 Stop Loss: {stop_loss:.2f}\n"
                       f"🎯 Target: {target:.2f} (RR 3.0)\n"
                       f"Risk: {risk:.2f} pts")
                print(msg)
                self.send_telegram(msg)
                return

    def run(self):
        logging.info(f"Starting Live Scalper for {self.symbol}...")
        self.send_telegram(f"🤖 Nifty Scalper Started on {self.symbol} (RR 3.0)")
        
        while True:
            try:
                if self.fetch_data():
                    self.calculate_indicators()
                    self.check_signal()
            except Exception as e:
                logging.error(f"Itertation Error: {e}")
                
            logging.info("Sleeping for 60s...")
            time.sleep(60)

if __name__ == "__main__":
    bot = NiftyScalperLive()
    bot.run()
