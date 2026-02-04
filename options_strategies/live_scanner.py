
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
    IndexConfig("NIFTY", "^NSEI", 25, 500, 200, 50),
    IndexConfig("BANKNIFTY", "^NSEBANK", 15, 1000, 500, 100)
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
            vix = last_row['vix']
            
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
                         
                         # Theoretical Max Risk (Width - Credit)
                         theor_risk = ((cfg.width) - entry_cost) * cfg.lot_size 
                         
                         # Managed Risk (Stop Loss @ 2x Limit)
                         # We exit if loss = 2x Premium Collected? No, usually exit if premium doubles.
                         # Stop Loss = 2 * Credit. Net Loss = Credit (Received) - 2*Credit (Paid to Close) = -Credit.
                         # Wait, standard "2x Stop" means if we sold for 100, we buy back at 200 (Loss 100).
                         # Effective Risk = Premium Received.
                         # If we set stop at 3x, risk is 2x Premium.
                         
                         # Our Backtest Logic: Stop @ 2.0 * Premium Value (i.e., loss = 2 * Premium)
                         # Example: Sold @ 1000. Stop when PnL = -2000. (i.e. Buy back @ 3000? No that's extreme).
                         # Let's clarify: stop_loss amount = max_profit * 2.0
                         # If Max Profit = 1000. Stop Loss = 2000.
                         # Risk = 2000. Reward = 1000. R:R = 1:2.
                         
                         max_profit = credit_collected
                         managed_risk = max_profit * 2.0 # Based on backtest config
                         risk_type_label = "Managed Risk (Stop @ 2x)"

                    else: # Net Debit (Spreads)
                         # Debit Spreads usually defined risk = entry cost.
                         entry_cost = abs(entry_cost)
                         total_cost = entry_cost * cfg.lot_size
                         
                         max_profit = (cfg.width - entry_cost) * cfg.lot_size
                         
                         # Backtest Logic: Stop @ 50% of Premium Paid.
                         # Reward: 1.5x Cost.
                         # Risk: 0.5x Cost.
                         
                         managed_risk = total_cost * 0.5
                         target_reward = total_cost * 1.5
                         max_profit = target_reward # Display Target Profit, not theoretical max
                         risk_type_label = "Managed Risk (Stop @ 50%)"

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
                    
                    # Optional: Log to CSV/DB as 'Detected'
                    
        except Exception as e:
            logger.error(f"Error scanning {cfg.symbol}: {e}")

if __name__ == "__main__":
    run_live_scan()
