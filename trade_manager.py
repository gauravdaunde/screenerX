import pandas as pd
import yfinance as yf
from datetime import datetime
from trade_db import get_connection, log_trade, get_balance, close_trade_in_db
from alerts import AlertBot # Reuse for Telegram

# Configuration
CAPITAL_STOCK = 100000.0
CAPITAL_OPTION = 100000.0
MAX_TRADES_PER_TYPE = 5 
PER_TRADE_LIMIT = CAPITAL_STOCK / MAX_TRADES_PER_TYPE # 20k

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
    strategy = signal['strategy']
    
    # Detect Type
    inst_type = 'OPTION' if ('CE' in symbol or 'PE' in symbol) else 'STOCK'
    
    # 1. Check Max Trades Limit for this Type
    open_trades = get_open_trades(inst_type)
    if len(open_trades) >= MAX_TRADES_PER_TYPE:
        print(f"⚠️ Limit Reached: Already have {len(open_trades)} {inst_type} trades.")
        return

    # Check duplicate symbol
    if not open_trades.empty and symbol in open_trades['symbol'].values:
        print(f"⚠️ Skipping {symbol}: already open position.")
        return

    # 2. Check Global Funds
    balance = get_balance()
    if balance < PER_TRADE_LIMIT:
        print(f"❌ Insufficient funds ({balance}) for new trade.")
        return

    # 3. Calculate Quantity
    # Logic: Invest fixed amount (20k)
    qty = int(PER_TRADE_LIMIT // price)
    
    if qty == 0:
        print(f"❌ Price {price} too high for allocation {PER_TRADE_LIMIT}")
        return

    # 4. Log Trade (Paper Trade)
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
    msg = f"🆕 <b>TRADE EXECUTED (PAPER)</b>\n\n🟢 BUY {symbol}\nQty: {qty}\nPrice: {price}\nSL: {sl}\nTP: {tp}"
    alert_bot.send_message(msg)


def monitor_positions():
    """
    Check open positions against current price.
    Run this every 2 mins.
    """
    trades = get_open_trades()
    if trades.empty:
        print("No open positions.")
        return

    print(f"🔍 Monitoring {len(trades)} open positions...")
    
    for index, row in trades.iterrows():
        symbol = row['symbol']
        trade_id = row['id']
        # entry_price not needed (was row['entry_price'])
        sl = row['sl']
        tp = row['tp']
        signal_type = row['signal_type'] # BUY
        
        # Fetch current price
        try:
            ticker = f"{symbol}.NS"
            data = yf.download(ticker, period="1d", interval="15m", progress=False)
            if data.empty: 
                continue
                
            current_price = data['Close'].iloc[-1]
            
            # Check Exit Conditions (For BUY)
            exit_reason = None
            if signal_type == 'BUY':
                if current_price >= tp:
                    exit_reason = "TARGET HIT 🎯"
                elif current_price <= sl:
                    exit_reason = "STOP LOSS HIT 🛑"
            
            # Execute Exit
            if exit_reason:
                pnl = close_trade_in_db(trade_id, current_price, exit_reason)
                
                # Telegram Alert
                emoji = "🟢" if pnl > 0 else "🔴"
                msg = f"{exit_reason}\n\n{emoji} Closed {symbol}\nPrice: {current_price}\nPnL: ₹{pnl:.2f}"
                alert_bot.send_message(msg)
                
        except Exception as e:
            print(f"Error checking {symbol}: {e}")

if __name__ == "__main__":
    monitor_positions()
