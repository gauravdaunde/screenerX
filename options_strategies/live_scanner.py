
import sys
import os
import time

# Fix for ModuleNotFoundError when running as script
sys.path.append(os.getcwd())

import logging
from datetime import datetime, timedelta
import pandas as pd


from app.db.database import ensure_wallet_exists, log_trade, get_connection
from app.core.alerts import AlertBot
from options_strategies.core import IndexConfig, IronCondor, BullCallSpread, BearPutSpread, OptionPricer
from app.core.dhan_client import get_dhan_client

# Init Dhan
dhan_client = get_dhan_client()

def get_next_expiry(symbol: str) -> str:
    today = datetime.now()
    is_index = symbol in ["NIFTY", "BANKNIFTY"]
    
    if is_index:
        days_ahead = 3 - today.weekday()
        if days_ahead <= 0: days_ahead += 7
        next_expiry = today + timedelta(days=days_ahead)
        return next_expiry.strftime("%Y-%m-%d")
    else:
        import calendar
        last_day = calendar.monthrange(today.year, today.month)[1]
        last_date = datetime(today.year, today.month, last_day)
        offset = (last_date.weekday() - 3) % 7
        this_month_expiry = last_date - timedelta(days=offset)
        
        if today.date() > this_month_expiry.date():
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

# Extended IndexConfig to hold Dhan ID
class DhanConfig(IndexConfig):
    def __init__(self, symbol, ticker, strike_gap, width, wing_dist, lot_size, security_id, exchange_segment, instrument_type):
        super().__init__(symbol, ticker, strike_gap, width, wing_dist, lot_size)
        self.security_id = security_id
        self.exchange_segment = exchange_segment
        self.instrument_type = instrument_type

CONFIGS = [
    # Indices
    DhanConfig("NIFTY", "^NSEI", 75, 500, 200, 50, '13', 'IDX_I', 'INDEX'),
    DhanConfig("BANKNIFTY", "^NSEBANK", 30, 1000, 500, 100, '25', 'IDX_I', 'INDEX'),
    
    # Stocks
    DhanConfig("HDFCBANK", "HDFCBANK.NS", 550, 30, 10, 10, '1333', 'NSE_EQ', 'EQUITY'),
    DhanConfig("RELIANCE", "RELIANCE.NS", 250, 50, 20, 20, '2885', 'NSE_EQ', 'EQUITY'),
    DhanConfig("ICICIBANK", "ICICIBANK.NS", 1250, 40, 20, 20, '4963', 'NSE_EQ', 'EQUITY'),
    DhanConfig("INFY", "INFY.NS", 400, 40, 20, 20, '1594', 'NSE_EQ', 'EQUITY'),
    DhanConfig("ITC", "ITC.NS", 1600, 15, 5, 5, '1660', 'NSE_EQ', 'EQUITY'),
    DhanConfig("LT", "LT.NS", 500, 100, 50, 50, '11483', 'NSE_EQ', 'EQUITY'),
    DhanConfig("TCS", "TCS.NS", 175, 100, 50, 50, '11536', 'NSE_EQ', 'EQUITY'),
    DhanConfig("AXISBANK", "AXISBANK.NS", 625, 30, 10, 10, '5900', 'NSE_EQ', 'EQUITY'),
    DhanConfig("BHARTIARTL", "BHARTIARTL.NS", 475, 40, 20, 20, '10604', 'NSE_EQ', 'EQUITY'),
    DhanConfig("SBIN", "SBIN.NS", 1500, 20, 5, 5, '3045', 'NSE_EQ', 'EQUITY')
]

# VIX Config
VIX_ID = '21'

class LiveDataManager:
    @staticmethod
    def fetch_recent_data(cfg, days=60) -> pd.DataFrame:
        if not dhan_client: return pd.DataFrame()
        
        to_date = datetime.now().strftime('%Y-%m-%d')
        from_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        try:
            # Fetch Stock/Index Data
            res = dhan_client.historical_daily_data(
                security_id=cfg.security_id,
                exchange_segment=cfg.exchange_segment,
                instrument_type=cfg.instrument_type,
                from_date=from_date,
                to_date=to_date
            )
            
            # Rate Limit Check
            if res.get('status') == 'failure' and 'Rate_Limit' in str(res):
                 time.sleep(1) # Extra Sleep if hit
                 
            if res.get('status') != 'success' or not res.get('data'):
                logging.error(f"Dhan Fetch Fail {cfg.symbol}: {res}")
                return pd.DataFrame()
                
            data = res['data']
            df = pd.DataFrame(data)
            
            # Timestamp handling
            if 'start_Time' in df.columns:
                 df['datetime'] = pd.to_datetime(df['start_Time'], unit='s')
            elif 'timestamp' in df.columns:
                 df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
            elif 'k' in df.columns:
                 df['datetime'] = pd.to_datetime(df['k'], unit='s')
                 
            df = df.set_index('datetime')
            
            rename = {'o':'open','h':'high','l':'low','c':'close','v':'volume'}
            df = df.rename(columns=rename)
            df = df[['open','high','low','close']].astype(float)
            
            # Fetch VIX
            vix_res = dhan_client.historical_daily_data(
                security_id=VIX_ID, exchange_segment='IDX_I', instrument_type='INDEX',
                from_date=from_date, to_date=to_date
            )
            
            vix_df = pd.DataFrame()
            if vix_res.get('status') == 'success' and vix_res.get('data'):
                vix_data = vix_res['data']
                vix_df = pd.DataFrame(vix_data)
                
                if 'start_Time' in vix_df.columns:
                     vix_df['datetime'] = pd.to_datetime(vix_df['start_Time'], unit='s')
                elif 'timestamp' in vix_df.columns:
                     vix_df['datetime'] = pd.to_datetime(vix_df['timestamp'], unit='s')
                elif 'k' in vix_df.columns:
                     vix_df['datetime'] = pd.to_datetime(vix_df['k'], unit='s')
                
                vix_df = vix_df.set_index('datetime')
                if 'c' in vix_df.columns:
                    vix_df = vix_df.rename(columns={'c': 'vix'})
                elif 'close' in vix_df.columns:
                    vix_df = vix_df.rename(columns={'close': 'vix'})
                vix_df = vix_df[['vix']].astype(float)
            
            # Merge
            if not vix_df.empty:
                df = df.join(vix_df, how='inner')
            else:
                df['vix'] = 15.0 
            
            # Indicators
            df['ema_20'] = df['close'].ewm(span=20).mean()
            df['ema_50'] = df['close'].ewm(span=50).mean()
            
            delta = df['close'].diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
            return df

        except Exception as e:
            logging.error(f"Data error {cfg.symbol}: {e}")
            return pd.DataFrame()

def calculate_pnl_update(trade_row, current_spot, current_vix, strategy_obj, cfg):
    try:
        entry_price = trade_row[2]
        qty = trade_row[3]
        anchor_strike = trade_row[4]
        expiry_date_str = trade_row[5]
        
        entry_cash_flow = entry_price 

        try:
            expiry_dt = datetime.strptime(expiry_date_str, "%Y-%m-%d")
        except:
            expiry_dt = datetime.now() + timedelta(days=5)
        
        days_to_expiry = (expiry_dt - datetime.now()).days

        legs = []
        if strategy_obj.name == "Iron Condor":
            base = anchor_strike
            legs = [
                {'strike': base + cfg.wing_dist, 'type': 'CE', 'side': 'SELL'},
                {'strike': base - cfg.wing_dist, 'type': 'PE', 'side': 'SELL'},
                {'strike': base + cfg.wing_dist + cfg.width, 'type': 'CE', 'side': 'BUY'},
                {'strike': base - cfg.wing_dist - cfg.width, 'type': 'PE', 'side': 'BUY'}
            ]
        elif strategy_obj.name == "Bull Call Spread":
            base = anchor_strike
            legs = [{'strike': base, 'type': 'CE', 'side': 'BUY'}, {'strike': base + cfg.width, 'type': 'CE', 'side': 'SELL'}]
        elif strategy_obj.name == "Bear Put Spread":
            base = anchor_strike
            legs = [{'strike': base, 'type': 'PE', 'side': 'BUY'}, {'strike': base - cfg.width, 'type': 'PE', 'side': 'SELL'}]

        exit_cash_flow = 0
        for leg in legs:
             prem = OptionPricer.get_premium(current_spot, leg['strike'], leg['type'], days_to_expiry, current_vix)
             if leg['side'] == 'BUY':
                 exit_cash_flow += prem 
             else:
                 exit_cash_flow -= prem 

        pnl_per_unit = entry_cash_flow + exit_cash_flow
        total_pnl = pnl_per_unit * qty

        invested = 0
        if entry_cash_flow < 0: invested = abs(entry_cash_flow) * qty
        else: invested = cfg.width * qty
        
        pnl_pct = 0.0
        if invested > 0: pnl_pct = (total_pnl / invested) * 100

        return total_pnl, pnl_pct
    except Exception as e:
        logging.error(f"PnL Calc Error: {e}")
        return 0, 0

def run_live_scan():
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger("LiveOptionsDhan")
    alert_bot = AlertBot()
    ensure_wallet_exists(BASE_STRATEGY_CATEGORY)

    scanned = 0
    errors = 0
    pnl_updates = []

    for cfg in CONFIGS:
        logger.info(f"Scanning {cfg.symbol} (Dhan)...")
        time.sleep(1) # Rate Limit Protection
        
        try:
            df = LiveDataManager.fetch_recent_data(cfg)
            if df.empty:
                logger.warning(f"No data for {cfg.symbol}")
                errors += 1
                continue
            
            scanned += 1
            last_row = df.iloc[-1]
            prev_row = df.iloc[-2]
            spot = last_row['close']
            
            is_index = cfg.symbol in ["NIFTY", "BANKNIFTY"]
            vix = last_row['vix'] if is_index else last_row['vix'] * 1.2
            
            existing_trade = None
            with get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, signal_type, entry_price, quantity, strike_price, expiry_date FROM trades WHERE symbol = ? AND strategy LIKE ? AND status = 'OPEN'", 
                    (cfg.symbol, f"{BASE_STRATEGY_CATEGORY}%")
                )
                existing_trade = cursor.fetchone()

            strategies = [IronCondor(cfg), BullCallSpread(cfg), BearPutSpread(cfg)]

            if existing_trade:
                t_id, s_type = existing_trade[0], existing_trade[1]
                strat_obj = None
                trade_strat = s_type.split(":")[1].replace(" ", "").upper() if ":" in s_type else s_type.upper()
                
                for s in strategies:
                    if s.name.replace(" ", "").upper() == trade_strat:
                        strat_obj = s
                        break
                
                if strat_obj:
                    pnl_val, pnl_pct = calculate_pnl_update(existing_trade, spot, vix, strat_obj, cfg)
                    from app.db.database import update_trade_pnl
                    update_trade_pnl(t_id, pnl_val)
                    logger.info(f"Updated PnL {cfg.symbol}: {pnl_val:.2f}")
                    pnl_updates.append(f"{cfg.symbol}: ₹{pnl_val:.0f} ({pnl_pct:.1f}%)")

            for strat in strategies:
                if not existing_trade:
                    # Check daily signal frequency
                    with get_connection() as conn:
                        cursor = conn.cursor()
                        today = datetime.now().replace(hour=0,minute=0,second=0)
                        cursor.execute("SELECT id FROM trades WHERE symbol=? AND signal_type=? AND entry_time>=?", (cfg.symbol, f"ENTER:{strat.name.upper()}", today))
                        if cursor.fetchone(): continue

                signal = strat.get_signal(last_row, prev_row)
                
                if signal['action'] == 'ENTER':
                    if existing_trade:
                        if trade_strat == strat.name.replace(" ", "").upper():
                             pnl_val, pnl_pct = calculate_pnl_update(existing_trade, spot, vix, strat, cfg)
                             status_str = "PROFIT" if pnl_val >= 0 else "LOSS"
                             emoji = "🟢" if pnl_val >= 0 else "🔴"
                             msg = (f"{emoji} <b>UPDATE: {cfg.symbol} {strat.name}</b>\n"
                                    f"Signal Valid. PnL: {pnl_pct:.1f}% ({status_str} ₹{abs(pnl_val):.0f})")
                             alert_bot.send_message(msg)
                    else:
                        logger.info(f"Signal: {strat.name} for {cfg.symbol}")
                        legs = strat.create_legs(spot, vix)
                        
                        entry_cost = 0
                        legs_str = ""
                        for leg in legs:
                            legs_str += f"\n • {leg['side']} {leg['strike']} {leg['type']} @ {leg['price']:.1f}"
                            if leg['side'] == 'BUY': entry_cost -= leg['price']
                            else: entry_cost += leg['price']
                        
                        target_cap = CAPITAL_ALLOCATION * 0.25
                        cap_per_lot = (cfg.width if entry_cost>0 else abs(entry_cost)) * cfg.lot_size
                        num_lots = max(1, min(int(target_cap/cap_per_lot), 10)) if cap_per_lot>0 else 1
                        total_qty = num_lots * cfg.lot_size
                        
                        msg = (f"🦅 <b>NEW TRADE (Dhan): {cfg.symbol}</b>\n"
                               f"Strat: {strat.name}\n"
                               f"Spot: {spot:.0f} | VIX: {vix:.2f}\n"
                               f"{legs_str}\n\n"
                               f"Qty: {num_lots} Lots\n"
                               f"Conf: {signal.get('confidence')}%")
                        alert_bot.send_message(msg)
                        
                        anchor = legs[0]['strike']
                        expiry = get_next_expiry(cfg.symbol)
                        log_trade(cfg.symbol, BASE_STRATEGY_CATEGORY, f"ENTER:{strat.name.upper()}", -entry_cost, total_qty, 0, 0, "OPTION", anchor, expiry)
                        break

        except Exception as e:
            logger.error(f"Error {cfg.symbol}: {e}")
            errors += 1
            
    summary = f"🏁 <b>Scan Complete (Dhan)</b>\nChecked: {scanned}\nErrors: {errors}"
    if pnl_updates:
        summary += "\n\n<b>PnL Updates:</b>\n" + "\n".join(pnl_updates)
    alert_bot.send_message(summary)

if __name__ == "__main__":
    run_live_scan()
