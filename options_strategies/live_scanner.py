
import sys
import os

# Fix for ModuleNotFoundError when running as script
sys.path.append(os.getcwd())

import logging
from datetime import datetime
import pandas as pd
import yfinance as yf
from app.db.database import ensure_wallet_exists, log_trade, get_connection
from app.core.alerts import AlertBot
from options_strategies.core import IndexConfig, IronCondor, BullCallSpread, BearPutSpread

# ==========================================
# CONFIGURATION
# ==========================================
CAPITAL_ALLOCATION = 100000.0
BASE_STRATEGY_CATEGORY = "SWING_OPTIONS"

CONFIGS = [
    # --- INDICES ---
    IndexConfig("NIFTY", "^NSEI", 75, 500, 200, 50),
    IndexConfig("BANKNIFTY", "^NSEBANK", 30, 1000, 500, 100),
    
    # --- TOP 10 NIFTY 50 STOCKS (By Weight) ---
    # Lot Sizes updated for Jan 2025
    
    # 1. HDFC Bank (~13%)
    IndexConfig("HDFCBANK", "HDFCBANK.NS", 550, 30, 10, 10),
    
    # 2. Reliance (~9%)
    IndexConfig("RELIANCE", "RELIANCE.NS", 250, 50, 20, 20),
    
    # 3. ICICI Bank (~7%)
    IndexConfig("ICICIBANK", "ICICIBANK.NS", 1250, 40, 20, 20),
    
    # 4. Infosys (~6%)
    IndexConfig("INFY", "INFY.NS", 400, 40, 20, 20),
    
    # 5. ITC (~4%)
    IndexConfig("ITC", "ITC.NS", 1600, 15, 5, 5),
    
    # 6. Larsen & Toubro (~4%)
    IndexConfig("LT", "LT.NS", 500, 100, 50, 50),
    
    # 7. TCS (~4%)
    IndexConfig("TCS", "TCS.NS", 175, 100, 50, 50),
    
    # 8. Axis Bank (~3%)
    IndexConfig("AXISBANK", "AXISBANK.NS", 625, 30, 10, 10),
    
    # 9. Bharti Airtel (~3%)
    IndexConfig("BHARTIARTL", "BHARTIARTL.NS", 475, 40, 20, 20),
    
    # 10. SBI (~3%)
    IndexConfig("SBIN", "SBIN.NS", 1500, 20, 5, 5)
]

# We need a DataManager that is similar to backtest but for live small window
class LiveDataManager:
    @staticmethod
    def fetch_recent_data(ticker: str, days=60) -> pd.DataFrame:
        """Fetch enough recent data to calculate indicators (EMA, RSI, BB)."""
        # Fetch Index
        try:
            index = yf.download(ticker, period=f"{days}d", interval="1d", progress=False)
            if hasattr(index.columns, "get_level_values") and isinstance(index.columns, pd.MultiIndex):
                index.columns = index.columns.get_level_values(0)
                
            index = index[['Close', 'Open', 'High', 'Low']]
            index.columns = ['close', 'open', 'high', 'low']
            
            # Fetch VIX
            vix = yf.download("^INDIAVIX", period=f"{days}d", interval="1d", progress=False)
            if hasattr(vix.columns, "get_level_values") and isinstance(vix.columns, pd.MultiIndex):
                vix.columns = vix.columns.get_level_values(0)
            
            # Merge
            df = index.join(vix['Close'].rename('vix'), how='inner')
            df.dropna(inplace=True)
            
            # Add Technicals
            df['ema_20'] = df['close'].ewm(span=20).mean()
            df['ema_50'] = df['close'].ewm(span=50).mean()
            
            # RSI
            delta = df['close'].diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
            return df
        except Exception as e:
            logging.error(f"Data fetch error for {ticker}: {e}")
            return pd.DataFrame()

def run_live_scan():
    """
    Scans for new signals for NIFTY and BANKNIFTY.
    Sends alerts if a signal is found and no conflicting position exists.
    """
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("LiveOptions")
    alert_bot = AlertBot()
    
    # ensure wallet for main Category
    ensure_wallet_exists(BASE_STRATEGY_CATEGORY)

    for cfg in CONFIGS:
        logger.info(f"Scanning {cfg.symbol}...")
        try:
            df = LiveDataManager.fetch_recent_data(cfg.ticker)
            if df.empty:
                logger.warning(f"No data for {cfg.symbol}")
                continue
                
            last_row = df.iloc[-1]
            prev_row = df.iloc[-2] # Assuming valid
            
            spot = last_row['close']
            
            # Stock VIX Adjustment
            is_index = cfg.symbol in ["NIFTY", "BANKNIFTY"]
            vix = last_row['vix'] if is_index else last_row['vix'] * 1.2
            
            strategies = [
                IronCondor(cfg),
                BullCallSpread(cfg),
                BearPutSpread(cfg)
            ]
            
            for strat in strategies:
                signal = strat.get_signal(last_row, prev_row)
                
                # Composite Strategy ID: SWING_OPTIONS:IronCondor
                composite_strategy_id = f"{BASE_STRATEGY_CATEGORY}:{strat.name.replace(' ', '')}"
                
                if signal['action'] == 'ENTER':
                    logger.info(f"✨ Signal Found: {strat.name} for {cfg.symbol}")
                    
                    # Generate Legs
                    legs = strat.create_legs(spot, vix)
                    
                    # Construct readable message
                    legs_str = ""
                    entry_cost = 0
                    for leg in legs:
                        legs_str += f"\n   • {leg['side']} {leg['strike']} {leg['type']} @ ₹{leg['price']:.1f}"
                        if leg['side'] == 'BUY':
                            entry_cost -= leg['price'] # Debit
                        else:
                            entry_cost += leg['price'] # Credit
                            
                    # PnL Estimates with STOP LOSS Logic (Managed Risk)
                    max_profit = 0
                    managed_risk = 0
                    risk_type_label = ""
                    
                    if entry_cost > 0: # Net Credit (Iron Condor)
                         credit_collected = entry_cost * cfg.lot_size
                         
                         # Our Backtest Logic: Stop @ 2.0 * Premium Value (i.e., loss = 2 * Premium)
                         max_profit = credit_collected
                         managed_risk = max_profit * 2.0 
                         risk_type_label = "Managed Risk (Stop @ 2x Credit)"

                    else: # Net Debit (Spreads)
                         # Debit Spreads usually defined risk = entry cost.
                         entry_cost = abs(entry_cost)
                         total_cost = entry_cost * cfg.lot_size
                         
                         # Backtest Logic: Stop @ 50% of Premium Paid.
                         managed_risk = total_cost * 0.5
                         target_reward = total_cost * 1.5
                         max_profit = target_reward # Display Target Profit, not theoretical max
                         risk_type_label = "Managed Risk (Stop @ 50% Cost)"

                    risk_reward = f"Risk: ₹{managed_risk:.0f} | Target: ₹{max_profit:.0f} ({risk_type_label})"

                    # Send Alert
                    msg = (
                        f"🦅 <b>NEW OPTIONS TRADE: {cfg.symbol}</b>\n"
                        f"Strategy: <b>{strat.name}</b>\n"
                        f"Type: {BASE_STRATEGY_CATEGORY}\n\n"
                        f"Spot: {spot:.0f} | VIX: {vix:.2f}\n"
                        f"{legs_str}\n\n"
                        f"💰 {risk_reward}\n"
                        f"Lot Size: {cfg.lot_size}\n"
                        f"Conf: {signal.get('confidence', 0)}%"
                    )
                    
                    # Send
                    alert_bot.send_message(msg)
                    logger.info(f"Alert Sent for {cfg.symbol} {strat.name}")
                    
        except Exception as e:
            logger.error(f"Error scanning {cfg.symbol}: {e}")

if __name__ == "__main__":
    run_live_scan()
