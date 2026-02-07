from datetime import datetime
import pandas as pd
import os
import sys
import time
import yfinance as yf

# Try imports
try:
    from app.db.database import get_connection, log_trade, get_balance, close_trade_in_db
    from app.core.alerts import AlertBot  # Reuse for Telegram
    from app.core.constants import SECURITY_IDS
except ImportError:
    # Append root if needed
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from app.db.database import get_connection, log_trade, get_balance, close_trade_in_db
    from app.core.alerts import AlertBot
    from app.core.constants import SECURITY_IDS

from dhanhq import dhanhq
from dotenv import load_dotenv

# Load Env
load_dotenv(".env")
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")

# Initialize Dhan
dhan_client = None
if DHAN_CLIENT_ID and DHAN_ACCESS_TOKEN:
    try:
        dhan_client = dhanhq(DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN)
        dhan_client.base_url = "https://api.dhan.co/v2"
    except Exception as e:
        print(f"Dhan init error: {e}")

# Configuration
CAPITAL_STOCK = 100000.0  # Old Swing Strategy
CAPITAL_SMART = 100000.0  # New Smart Strategy
MAX_TRADES_PER_TYPE = 5 
PER_TRADE_LIMIT = CAPITAL_STOCK / MAX_TRADES_PER_TYPE # 20k

# Smart Strategy Config
SMART_MAX_HOLD_DAYS = 30
SMART_BE_TRIGGER = 0.70
SMART_TRAIL_DIST = 0.015

alert_bot = AlertBot()

def get_open_trades(instrument_type=None):
    conn = get_connection()
    query = "SELECT * FROM trades WHERE status = 'OPEN'"
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    # Filter by type (assuming we will add 'type' column later or infer it)
    # For now, we assume all trades are STOCK unless symbol implies otherwise
    if not df.empty:
        df['type'] = df['symbol'].apply(lambda x: 'OPTION' if 'CE' in x or 'PE' in x else 'STOCK')
        if instrument_type:
            df = df[df['type'] == instrument_type]
            
    return df

def execute_trade(signal):
    """
    Execute a trade based on signal.
    """
    symbol = signal['symbol']
    price = signal['price']
    action = signal['signal']
    sl = signal['stop_loss']
    tp = signal['target']
    strategy = signal.get('strategy', 'SWING')
    
    # Capital Allocation & Limits
    if strategy == 'SWING_SMART':
        max_slots = MAX_TRADES_PER_TYPE
        allocation_per_trade = CAPITAL_SMART / max_slots
    else:
        max_slots = MAX_TRADES_PER_TYPE
        allocation_per_trade = CAPITAL_STOCK / max_slots

    # Get Open Trades
    # We execute mostly STOCK trades here.
    open_trades = get_open_trades('STOCK')
    
    # Filter for Specific Strategy Count
    if not open_trades.empty:
        if strategy == 'SWING_SMART':
            active_trades = open_trades[open_trades['strategy'] == 'SWING_SMART']
        else:
            # Count anything NOT smart as standard SWING
            active_trades = open_trades[open_trades['strategy'] != 'SWING_SMART']
            
        current_count = len(active_trades)
        
        # 1. Check Max Limit
        if current_count >= max_slots:
            print(f"⚠️ Limit Reached for {strategy}: {current_count}/{max_slots} slots full.")
            return

        # 2. Check Duplicate Symbol (Global check, don't buy same stock twice across strategies ideally)
        if symbol in open_trades['symbol'].values:
            print(f"⚠️ Skipping {symbol}: already open position.")
            return
    else:
        current_count = 0

    # 3. Check Global Funds (Sanity Check)
    balance = get_balance()
    if balance < allocation_per_trade:
        print(f"❌ Insufficient funds ({balance}) for new trade.")
        return

    # 4. Calculate Quantity
    qty = int(allocation_per_trade // price)
    
    if qty == 0:
        print(f"❌ Price {price} too high for allocation {allocation_per_trade}")
        return

    # 5. Log Trade (Paper Trade)
    log_trade(
        symbol=symbol,
        strategy=strategy,
        signal_type=action, 
        price=price, 
        qty=qty, 
        sl=sl, 
        tp=tp
    )
    
    # Send Telegram
    smart_tag = " [SMART]" if strategy == 'SWING_SMART' else ""
    msg = f"🆕 <b>TRADE EXECUTED{smart_tag}</b>\n\n🟢 BUY {symbol}\nQty: {qty}\nPrice: {price}\nSL: {sl}\nTP: {tp}"
    alert_bot.send_message(msg)


def fetch_current_price(symbol: str) -> float:
    """
    Fetch current price.
    Primary: Dhan API (15m delay interval)
    Fallback: Yahoo Finance (Live-ish)
    """
    price = 0.0
    
    # --- 1. Try Dhan ---
    if dhan_client:
        security_id = SECURITY_IDS.get(symbol)
        if security_id:
            try:
                to_date = datetime.now().strftime('%Y-%m-%d')
                from_date = (datetime.now() - pd.Timedelta(days=3)).strftime('%Y-%m-%d')
                
                # Use 15m interval (less data) but recent
                res = dhan_client.intraday_minute_data(
                    security_id=security_id,
                    exchange_segment='NSE_EQ',
                    instrument_type='EQUITY',
                    from_date=from_date,
                    to_date=to_date,
                    interval=15 
                )
                
                if res.get('status') == 'success' and res.get('data'):
                    data = res['data']
                    if data:
                        last_candle = data[-1]
                        price = float(last_candle.get('c', 0.0))
                        if price > 0:
                            return price
            except Exception as e:
                # print(f"Dhan price fetch failed: {e}")
                pass
    
    # --- 2. Fallback to YFinance ---
    try:
        ticker = f"{symbol}.NS"
        # Fast fetch
        data = yf.download(ticker, period="1d", interval="1m", progress=False)
        if not data.empty:
             val = data['Close'].iloc[-1]
             # Handle Series or scalar
             if isinstance(val, pd.Series):
                 val = val.iloc[0] # Should be scalar if iloc[-1] on Series, wait.
                 # If DataFrame.iloc[-1] returns Series (row). ['Close'] returns scalar.
                 # But new yfinance might return MultiIndex columns.
                 pass
             
             # If MultiIndex columns (Price, Ticker)
             if isinstance(data.columns, pd.MultiIndex):
                 # Close -> Ticker
                 # We need to access properly
                 scalar = data['Close'].iloc[-1].values[0] if hasattr(data['Close'].iloc[-1], 'values') else data['Close'].iloc[-1]
                 return float(scalar)
             
             return float(val)
             
    except Exception as e:
        print(f"YFinance fallback failed for {symbol}: {e}")
        
    return 0.0


def monitor_positions():
    """
    Real-Time Trade Management Loop
    ===============================
    
    Monitors all open positions and handles exits.
    """
    trades = get_open_trades()
    if trades.empty:
        print("No open positions.")
        return

    print(f"🔍 Monitoring {len(trades)} open positions...")
    
    if not dhan_client:
         print("⚠️ Dhan Client not active. Relying on Fallbacks.")
    
    total_unrealized_pnl = 0.0
    
    for index, row in trades.iterrows():
        symbol = row['symbol']
        trade_id = row['id']
        strategy = row.get('strategy', 'SWING') # Default to old
        
        # SKIP OPTION STRATEGIES (Managed by live_scanner.py Updates)
        if strategy == 'SWING_OPTIONS' or strategy.startswith('SWING_OPTIONS'):
            continue
            
        sl = row['sl']
        tp = row['tp']
        signal_type = row['signal_type'] # BUY
        entry_price = row['entry_price']
        entry_date = pd.to_datetime(row['entry_time'])
        
        # Rate Limit Prevention (Dhan)
        time.sleep(1)

        # Fetch current price
        current_price = fetch_current_price(symbol)
            
        if current_price <= 0:
            print(f"No price data for {symbol}")
            continue
            
        # Calculate Unrealized PnL for this trade
        qty = row['quantity']
        # Assuming BUY triggers
        trade_pnl = (current_price - entry_price) * qty
        total_unrealized_pnl += trade_pnl
        
        exit_reason = None
        
        # ==========================================
        # 🧠 SMART STRATEGY LOGIC
        # ==========================================
        if strategy == 'SWING_SMART':
            # Time Exit (30 Days)
            days_held = (datetime.now() - entry_date).days
            if days_held >= SMART_MAX_HOLD_DAYS:
                exit_reason = f"MAX HOLD ({days_held} days)"
            
            else:
                if current_price <= sl:
                        exit_reason = "STOP LOSS HIT 🛑"
                
                # Trail Activation (After Target Hit)
                elif current_price >= tp:
                        # Temporary: Treat TP as TP.
                        exit_reason = "TARGET HIT 🎯 (Smart)" 

        # ==========================================
        # 👴 OLD STRATEGY LOGIC
        # ==========================================
        else:
            if current_price >= tp:
                exit_reason = "TARGET HIT 🎯"
            elif current_price <= sl:
                exit_reason = "STOP LOSS HIT 🛑"
        
        # Execute Exit
        if exit_reason:
            pnl = close_trade_in_db(trade_id, current_price, exit_reason)
            
            # Telegram Alert
            emoji = "🟢" if pnl > 0 else "🔴"
            strat_tag = " [SMART]" if strategy == 'SWING_SMART' else ""
            msg = f"{exit_reason}{strat_tag}\n\n{emoji} Closed {symbol}\nPrice: {current_price}\nPnL: ₹{pnl:.2f}"
            alert_bot.send_message(msg)

    # Log Portfolio Summary
    equity = get_balance() + total_unrealized_pnl
    print("-" * 40)
    print(f"💰 Unrl. PnL: ₹{total_unrealized_pnl:,.2f}")
    print(f"🏦 Total Eqty: ₹{equity:,.2f}")
    print("✅ Monitoring Complete.")

if __name__ == "__main__":
    monitor_positions()
