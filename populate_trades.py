import sqlite3
import random
from datetime import datetime, timedelta

DB_NAME = "trades.db"

strategies = ["SuperTrend Pivot", "MACD Momentum", "BB Mean Reversion", "EMA Crossover", "Trend Pullback", "Swing Breakout"]
symbols = ["TATASTEEL", "RELIANCE", "INFY", "HDFCBANK", "SBIN", "ICICIBANK", "ITC", "BAJFINANCE", "ADANIENT", "BHARTIARTL", "LT", "HCLTECH"]

def get_connection():
    return sqlite3.connect(DB_NAME, timeout=10)

def update_balance(amount):
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT balance FROM account ORDER BY id DESC LIMIT 1')
    result = c.fetchone()
    if result:
        current = result[0]
        new_bal = current + amount
        c.execute('UPDATE account SET balance = ?, updated_at = ? WHERE id = 1', (new_bal, datetime.now()))
    else:
        # Should not happen if initialized, but just in case
        print("Account not found, skipping balance update")
        
    conn.commit()
    conn.close()

def generate_trades():
    conn = get_connection()
    c = conn.cursor()
    
    start_date = datetime.now() - timedelta(days=45)
    total_inserted_pnl = 0
    
    print("Generating ~40 historical trades...")
    
    for i in range(40):
        strategy = random.choice(strategies)
        symbol = random.choice(symbols)
        signal = random.choice(["BUY", "SELL"])
        
        # Spread dates over last 45 days
        days_ago_entry = random.randint(2, 45)
        entry_time = datetime.now() - timedelta(days=days_ago_entry)
        
        # Holding period 1-7 days
        days_hold = random.randint(1, 7)
        exit_time = entry_time + timedelta(days=days_hold)
        
        # Don't let exit time be in future
        if exit_time > datetime.now():
            # If it would end in future, define it as ending 'today' or recently
            # Or just skip/shorten
            exit_time = datetime.now() - timedelta(minutes=random.randint(10, 300))
        
        qty = random.choice([10, 25, 50, 100])
        # Random price approx range
        base_price = random.uniform(1000, 3000)
        entry_price = round(base_price, 2)
        
        # Calculate PnL based on Strategy Characteristic
        # SWING_SMART: High winrate, small steady gains
        # BB: Mean reversion, some losses
        # SuperTrend: Big wins, big losses
        
        rand_val = random.random()
        
        if strategy == "SWING_SMART":
            # 70% win rate
            if rand_val < 0.7:
                pct_change = random.uniform(0.02, 0.05) # 2-5% profit
            else:
                pct_change = random.uniform(-0.02, -0.01) # 1-2% loss
        elif strategy == "BB Mean Reversion":
            # 50% win rate
             if rand_val < 0.5:
                pct_change = random.uniform(0.03, 0.06)
             else:
                pct_change = random.uniform(-0.02, -0.04)
        else: # SuperTrend
            # 40% win rate but big runners
             if rand_val < 0.4:
                pct_change = random.uniform(0.05, 0.15) # Big win
             else:
                pct_change = random.uniform(-0.02, -0.05) # Normal stop loss
                
        # Calculate PnL absolut
        # For BUY: (Exit - Entry) * Qty
        # For SELL: (Entry - Exit) * Qty
        
        invested = entry_price * qty
        pnl = invested * pct_change
        
        if signal == "BUY":
            exit_price = entry_price + (pnl / qty)
        else:
            exit_price = entry_price - (pnl / qty)
            
        exit_price = round(exit_price, 2)
        pnl = round(pnl, 2)
        
        sl = round(entry_price * 0.95, 2)
        tp = round(entry_price * 1.05, 2)
        
        reason = "TARGET" if pnl > 0 else "STOPLOSS"
        
        c.execute('''
            INSERT INTO trades (symbol, strategy, signal_type, entry_price, quantity, entry_time, sl, tp, status, exit_price, exit_time, pnl, exit_reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (symbol, strategy, signal, entry_price, qty, entry_time, sl, tp, 'CLOSED', exit_price, exit_time, pnl, reason))
        
        total_inserted_pnl += pnl
        
    conn.commit()
    conn.close()
    
    print(f"✅ Trades inserted. Updating Balance by {total_inserted_pnl:,.2f}...")
    update_balance(total_inserted_pnl)
    print("DONE.")

if __name__ == "__main__":
    generate_trades()
