
import sys
import os

# Fix for ModuleNotFoundError when running as script
sys.path.append(os.getcwd())

import logging
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf
from app.db.database import ensure_wallet_exists, log_trade, get_connection
from app.core.alerts import AlertBot
from options_strategies.core import IndexConfig, IronCondor, BullCallSpread, BearPutSpread

def get_next_expiry(symbol: str) -> str:
    """
    Calculate next expiry date.
    Indices: Weekly (Next Thursday)
    Stocks: Monthly (Last Thursday of Current/Next Month)
    """
    today = datetime.now()
    
    # Simple Logic for now: 
    # If Index -> Target nearest Thursday
    # If Stock -> Target last Thursday of Month
    
    is_index = symbol in ["NIFTY", "BANKNIFTY"]
    
    if is_index:
        # Find next Thursday
        # weekday(): Mon=0 ... Thu=3
        days_ahead = 3 - today.weekday()
        if days_ahead <= 0: # Target next week if today is Fri/Sat/Sun or late Thu
             days_ahead += 7
        next_expiry = today + timedelta(days=days_ahead)
        return next_expiry.strftime("%Y-%m-%d")
    else:
        # Stocks: Last Thursday of current month
        # Start from last day of month and go back until Thu
        # If today is past that, go to next month
        
        # Simplified: Project 25 days ahead and find nearest Thursday? 
        # Better: Current Month Expiry
        
        # Find Last Thursday of this month
        import calendar
        last_day = calendar.monthrange(today.year, today.month)[1]
        last_date = datetime(today.year, today.month, last_day)
        
        offset = (last_date.weekday() - 3) % 7
        this_month_expiry = last_date - timedelta(days=offset)
        
        if today.date() > this_month_expiry.date():
             # Move to next month
             if today.month == 12:
                 next_month = 1
                 year = today.year + 1
             else:
                 next_month = today.month + 1
                 year = today.year
                 
             last_day_next = calendar.monthrange(year, next_month)[1]
             last_date_next = datetime(year, next_month, last_day_next)
             offset_next = (last_date_next.weekday() - 3) % 7
             final_expiry = last_date_next - timedelta(days=offset_next)
             return final_expiry.strftime("%Y-%m-%d")
        
        return this_month_expiry.strftime("%Y-%m-%d")

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
        # Check for existing open position to prevent duplicates
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id FROM trades WHERE symbol = ? AND strategy LIKE ? AND status = 'OPEN'", 
                (cfg.symbol, f"{BASE_STRATEGY_CATEGORY}%")
            )
            if cursor.fetchone():
                logger.info(f"Skipping {cfg.symbol}: Open Position Exists.")
                continue

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
                # composite_strategy_id = f"{BASE_STRATEGY_CATEGORY}:{strat.name.replace(' ', '')}"
                
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

                    # Capture raw cost for logging (Negative = Debit, Positive = Credit)
                    raw_entry_cost = entry_cost
                            
                    # Position Sizing
                    # Target Deployment per trade (e.g. 25% of 100k = 25k)
                    PER_TRADE_ALLOCATION_PCT = 0.25
                    target_capital = CAPITAL_ALLOCATION * PER_TRADE_ALLOCATION_PCT
                    
                    capital_per_lot = 0.0
                    if entry_cost > 0: # Credit Strategy (Margin Blocking)
                        # Approx Margin = Spread Width * Lot Size
                        capital_per_lot = cfg.width * cfg.lot_size
                    else: # Debit Strategy (Premium Paid)
                        capital_per_lot = abs(entry_cost) * cfg.lot_size
                        
                    # Calculate Lots (Floor)
                    num_lots = 1
                    if capital_per_lot > 0:
                        num_lots = int(target_capital / capital_per_lot)
                        
                    # Safety bounds
                    num_lots = max(1, min(num_lots, 10)) # Min 1, Max 10 lots
                    
                    total_qty = num_lots * cfg.lot_size
                    
                    # Log sizing decision
                    logger.info(f"Sizing: Target ₹{target_capital/1000:.1f}k | Cost/Lot ₹{capital_per_lot/1000:.1f}k -> {num_lots} Lots")

                    # PnL Estimates with STOP LOSS Logic (Managed Risk)
                    max_profit = 0
                    managed_risk = 0
                    risk_type_label = ""
                    
                    if entry_cost > 0: # Net Credit (Iron Condor)
                         credit_collected = entry_cost * total_qty
                         
                         # Our Backtest Logic: Stop @ 2.0 * Premium Value (i.e., loss = 2 * Premium)
                         max_profit = credit_collected
                         managed_risk = max_profit * 2.0 
                         risk_type_label = "Managed Risk (Stop @ 2x Credit)"

                    else: # Net Debit (Spreads)
                         # Debit Spreads usually defined risk = entry cost.
                         entry_cost = abs(entry_cost)
                         total_cost = entry_cost * total_qty
                         
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
                        f"� <b>Position Size: {num_lots} Lots ({total_qty} Qty)</b>\n"
                        f"💰 {risk_reward}\n"
                        f"Conf: {signal.get('confidence', 0)}%"
                    )
                    
                    # Send
                    alert_bot.send_message(msg)
                    logger.info(f"Alert Sent for {cfg.symbol} {strat.name}")

                    # Log Trade to Database
                    # Note: log_trade expects price to be positive for Buy (Debit), so we flip sign of raw_entry_cost
                    # If raw_entry_cost is negative (Debit), price = positive (deducted).
                    # If raw_entry_cost is positive (Credit), price = negative (added).
                    trade_price = -raw_entry_cost
                    
                    # Determine Anchor Strike
                    # For Iron Condor: Center Base (Spot Rounding)
                    # For Spreads: The Buy Leg Strike
                    anchor_strike = 0.0
                    if strat.name == "Iron Condor":
                        anchor_strike = round(spot / cfg.strike_gap) * cfg.strike_gap
                    else:
                        # Find the BUY leg
                        for l in legs:
                            if l['side'] == 'BUY':
                                anchor_strike = l['strike']
                                break
                    
                    expiry_date = get_next_expiry(cfg.symbol)

                    log_trade(
                        symbol=cfg.symbol,
                        strategy=BASE_STRATEGY_CATEGORY,
                        signal_type=f"ENTER:{strat.name.upper()}",
                        price=trade_price,
                        qty=total_qty,
                        sl=0, # Complex structure, SL is managed manually or via PnL check
                        tp=0,
                        asset_type="OPTION",
                        strike_price=anchor_strike,
                        expiry_date=expiry_date
                    )
                    
        except Exception as e:
            logger.error(f"Error scanning {cfg.symbol}: {e}")

if __name__ == "__main__":
    run_live_scan()
