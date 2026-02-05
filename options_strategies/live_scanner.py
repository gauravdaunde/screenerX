
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
from options_strategies.core import IndexConfig, IronCondor, BullCallSpread, BearPutSpread, OptionPricer

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

def calculate_pnl_update(trade_row, current_spot, current_vix, strategy_obj, config):
    try:
        # trade_row: (id, signal_type, entry_price, quantity, strike_price, expiry_date)
        entry_price = trade_row[2]
        qty = trade_row[3]
        anchor_strike = trade_row[4]
        expiry_date_str = trade_row[5]

        # Entry Cash Flow per unit
        # stored price is -net_cost. So net_cost = -price.
        entry_cash_flow = -entry_price

        # Days to expiry
        try:
            expiry_dt = datetime.strptime(expiry_date_str, "%Y-%m-%d")
        except:
            # Fallback if expiry not parsed
            expiry_dt = datetime.now() + timedelta(days=5)

        days_to_expiry = (expiry_dt - datetime.now()).days

        # Reconstruct Legs
        legs = []
        if strategy_obj.name == "Iron Condor":
            base = anchor_strike
            sc_strike = base + config.wing_dist
            sp_strike = base - config.wing_dist
            lc_strike = sc_strike + config.width
            lp_strike = sp_strike - config.width
            legs = [
                {'strike': sc_strike, 'type': 'CE', 'side': 'SELL'},
                {'strike': sp_strike, 'type': 'PE', 'side': 'SELL'},
                {'strike': lc_strike, 'type': 'CE', 'side': 'BUY'},
                {'strike': lp_strike, 'type': 'PE', 'side': 'BUY'}
            ]
        elif strategy_obj.name == "Bull Call Spread":
            base = anchor_strike # Buy Leg is anchor
            bc_strike = base
            sc_strike = base + config.width
            legs = [
                {'strike': bc_strike, 'type': 'CE', 'side': 'BUY'},
                {'strike': sc_strike, 'type': 'CE', 'side': 'SELL'}
            ]
        elif strategy_obj.name == "Bear Put Spread":
            base = anchor_strike # Buy Leg is anchor
            bp_strike = base
            sp_strike = base - config.width
            legs = [
                {'strike': bp_strike, 'type': 'PE', 'side': 'BUY'},
                {'strike': sp_strike, 'type': 'PE', 'side': 'SELL'}
            ]

        exit_cash_flow = 0
        for leg in legs:
             prem = OptionPricer.get_premium(current_spot, leg['strike'], leg['type'], days_to_expiry, current_vix)
             if leg['side'] == 'BUY':
                 exit_cash_flow += prem # Credit to sell
             else:
                 exit_cash_flow -= prem # Debit to buy back

        # PnL
        pnl_per_unit = entry_cash_flow + exit_cash_flow
        total_pnl = pnl_per_unit * qty

        # Invested (for ROI)
        invested = 0
        if entry_cash_flow < 0: # Debit Trade
            invested = abs(entry_cash_flow) * qty
        else: # Credit Trade (Margin)
            invested = config.width * qty

        pnl_pct = 0.0
        if invested > 0:
            pnl_pct = (total_pnl / invested) * 100

        return total_pnl, pnl_pct

    except Exception as e:
        logging.error(f"PnL calculation failed: {e}")
        return 0, 0

def run_live_scan():
    """
    Scans for new signals. If position exists, sends PnL update instead of new signal.
    """
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("LiveOptions")
    alert_bot = AlertBot()
    
    # ensure wallet for main Category
    ensure_wallet_exists(BASE_STRATEGY_CATEGORY)

    for cfg in CONFIGS:
        logger.info(f"Scanning {cfg.symbol}...")
        
        # 1. Fetch Data First (We need it for both new signals and PnL updates)
        try:
            df = LiveDataManager.fetch_recent_data(cfg.ticker)
            if df.empty:
                logger.warning(f"No data for {cfg.symbol}")
                continue
                
            last_row = df.iloc[-1]
            prev_row = df.iloc[-2]
            
            spot = last_row['close']
            
            # Stock VIX Adjustment
            is_index = cfg.symbol in ["NIFTY", "BANKNIFTY"]
            vix = last_row['vix'] if is_index else last_row['vix'] * 1.2
            
            # 2. Check for existing open position
            existing_trade = None
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, signal_type, entry_price, quantity, strike_price, expiry_date FROM trades WHERE symbol = ? AND strategy LIKE ? AND status = 'OPEN'", 
                    (cfg.symbol, f"{BASE_STRATEGY_CATEGORY}%")
                )
                existing_trade = cursor.fetchone() # Returns tuple or None

            strategies = [
                IronCondor(cfg),
                BullCallSpread(cfg),
                BearPutSpread(cfg)
            ]
            
            for strat in strategies:
                # Early check: If NO Open Position, did we already signal this strategy today?
                if not existing_trade:
                    with get_connection() as conn:
                        cursor = conn.cursor()
                        # Construct signal type string to match DB
                        sig_type_query = f"ENTER:{strat.name.upper()}"
                        
                        # Get start of today
                        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                        
                        cursor.execute(
                            "SELECT id FROM trades WHERE symbol = ? AND signal_type = ? AND entry_time >= ?", 
                            (cfg.symbol, sig_type_query, today_start)
                        )
                        if cursor.fetchone():
                            # Already signaled today (and presumably closed, since existing_trade is None)
                            logger.info(f"Skipping {strat.name} for {cfg.symbol}: Already signaled today.")
                            continue

                signal = strat.get_signal(last_row, prev_row)
                
                if signal['action'] == 'ENTER':
                    
                    if existing_trade:
                        # Unpack
                        # ID, Type, Price, Qty, Strike, Expiry
                        s_type = existing_trade[1] # e.g. "ENTER:IRON CONDOR"
                        
                        # Extract trade strategy name
                        # s_type format: "ENTER:STRAT NAME"
                        if ":" in s_type:
                            trade_strat_name = s_type.split(":")[1].replace(" ", "").upper()
                        else:
                            trade_strat_name = s_type.upper()
                            
                        current_strat_name = strat.name.replace(" ", "").upper()
                        
                        if trade_strat_name == current_strat_name:
                            # SAME Strategy Signaling Again -> Send Update
                            pnl_val, pnl_pct = calculate_pnl_update(existing_trade, spot, vix, strat, cfg)
                            
                            status_str = "PROFIT" if pnl_val >= 0 else "LOSS"
                            emoji = "🟢" if pnl_val >= 0 else "🔴"
                            
                            msg = (
                                f"{emoji} <b>UPDATE: {cfg.symbol} {strat.name}</b>\n"
                                f"Signal Valid. Existing Position Status:\n"
                                f"PnL: {pnl_pct:.1f}% ({status_str} ₹{abs(pnl_val):.0f})\n"
                                f"Spot: {spot:.0f} | VIX: {vix:.2f}"
                            )
                            alert_bot.send_message(msg)
                            logger.info(f"Sent PnL Update for {cfg.symbol} {strat.name}: {pnl_val}")
                            
                        else:
                            # Different strategy signaling but one is open. Skip.
                            logger.info(f"Skipping {strat.name} for {cfg.symbol}: Conflict with Open Trade ({trade_strat_name}).")
                            
                    else:
                        # NO Open Position -> Execute Entry Logic (Original Code)
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

                        raw_entry_cost = entry_cost
                                
                        # Position Sizing
                        PER_TRADE_ALLOCATION_PCT = 0.25
                        target_capital = CAPITAL_ALLOCATION * PER_TRADE_ALLOCATION_PCT
                        
                        capital_per_lot = 0.0
                        if entry_cost > 0: 
                            capital_per_lot = cfg.width * cfg.lot_size
                        else: 
                            capital_per_lot = abs(entry_cost) * cfg.lot_size
                            
                        num_lots = 1
                        if capital_per_lot > 0:
                            num_lots = int(target_capital / capital_per_lot)
                            
                        num_lots = max(1, min(num_lots, 10))
                        total_qty = num_lots * cfg.lot_size
                        
                        # PnL Estimates
                        max_profit = 0
                        managed_risk = 0
                        risk_type_label = ""
                        
                        if entry_cost > 0: # Net Credit
                             credit_collected = entry_cost * total_qty
                             max_profit = credit_collected
                             managed_risk = max_profit * 2.0 
                             risk_type_label = "Managed Risk (Stop @ 2x Credit)"
                        else: # Net Debit
                             entry_cost_abs = abs(entry_cost)
                             total_cost = entry_cost_abs * total_qty
                             managed_risk = total_cost * 0.5
                             target_reward = total_cost * 1.5
                             max_profit = target_reward 
                             risk_type_label = "Managed Risk (Stop @ 50% Cost)"

                        risk_reward = f"Risk: ₹{managed_risk:.0f} | Target: ₹{max_profit:.0f} ({risk_type_label})"

                        # Send Alert
                        msg = (
                            f"🦅 <b>NEW OPTIONS TRADE: {cfg.symbol}</b>\n"
                            f"Strategy: <b>{strat.name}</b>\n"
                            f"Type: {BASE_STRATEGY_CATEGORY}\n\n"
                            f"Spot: {spot:.0f} | VIX: {vix:.2f}\n"
                            f"{legs_str}\n\n"
                            f"📦 <b>Position Size: {num_lots} Lots ({total_qty} Qty)</b>\n"
                            f"💰 {risk_reward}\n"
                            f"Conf: {signal.get('confidence', 0)}%"
                        )
                        
                        alert_bot.send_message(msg)
                        logger.info(f"Alert Sent for {cfg.symbol} {strat.name}")

                        # Log Trade
                        trade_price = -raw_entry_cost
                        
                        anchor_strike = 0.0
                        if strat.name == "Iron Condor":
                            anchor_strike = round(spot / cfg.strike_gap) * cfg.strike_gap
                        elif strat.name == "Bull Call Spread" or strat.name == "Bear Put Spread":
                             # Start of legs usually has the anchor, but let's be safe
                             # Bull Call: Buy Base, Sell Higher
                             # Bear Put: Buy Base, Sell Lower
                             # In existing code for spreads, "base" is used for Buy leg.
                             # legs[0] is Buy Base for Bull Call
                             # legs[0] is Buy Base for Bear Put
                            anchor_strike = legs[0]['strike']  
                        else:
                            # Fallback
                            anchor_strike = legs[0]['strike']

                        expiry_date = get_next_expiry(cfg.symbol)

                        log_trade(
                            symbol=cfg.symbol,
                            strategy=BASE_STRATEGY_CATEGORY,
                            signal_type=f"ENTER:{strat.name.upper()}",
                            price=trade_price,
                            qty=total_qty,
                            sl=0, 
                            tp=0,
                            asset_type="OPTION",
                            strike_price=anchor_strike,
                            expiry_date=expiry_date
                        )
                        
                        # Break strategies loop for this symbol to avoid multiple opening on same symbol at same time
                        break
                        
        except Exception as e:
            logger.error(f"Error scanning {cfg.symbol}: {e}")

if __name__ == "__main__":
    run_live_scan()
