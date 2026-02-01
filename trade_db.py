import sqlite3
from datetime import datetime
import pandas as pd

DB_NAME = "trades.db"

def init_db():
    """Initialize the database tables (Production Reset)."""
    conn = sqlite3.connect(DB_NAME, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL;") 
    c = conn.cursor()
    
    # Optional: Drop tables if you want a complete reset for production
    # c.execute("DROP TABLE IF EXISTS trades")
    # c.execute("DROP TABLE IF EXISTS account")
    
    # Create Trades Table
    c.execute('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            strategy TEXT,
            signal_type TEXT, -- BUY / SELL
            entry_price REAL,
            quantity INTEGER,
            entry_time TIMESTAMP,
            sl REAL,
            tp REAL,
            status TEXT, -- OPEN, CLOSED
            exit_price REAL,
            exit_time TIMESTAMP,
            pnl REAL,
            exit_reason TEXT
        )
    ''')
    
    # Create Account Table 
    c.execute('''
        CREATE TABLE IF NOT EXISTS account (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            balance REAL DEFAULT 200000.0,
            updated_at TIMESTAMP
        )
    ''')
    
    # Initialize balance if not exists
    c.execute('SELECT count(*) FROM account')
    if c.fetchone()[0] == 0:
         # 100k Stocks + 100k Options
        c.execute('INSERT INTO account (balance, updated_at) VALUES (?, ?)', (200000.0, datetime.now()))
    
    conn.commit()
    conn.close()
    print("✅ Database initialized (WAL Mode Enabled).")

def get_connection():
    # Helper to get connection with proper timeout
    conn = sqlite3.connect(DB_NAME, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL;") 
    return conn

def get_balance():
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT balance FROM account ORDER BY id DESC LIMIT 1')
    bal = c.fetchone()[0]
    conn.close()
    return bal

def update_balance(amount_change):
    current = get_balance()
    new_bal = current + amount_change
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE account SET balance = ?, updated_at = ? WHERE id = 1', (new_bal, datetime.now()))
    conn.commit()
    conn.close()

def log_trade(symbol, strategy, signal_type, price, qty, sl, tp):
    conn = get_connection()
    c = conn.cursor()
    
    c.execute('''
        INSERT INTO trades (symbol, strategy, signal_type, entry_price, quantity, entry_time, sl, tp, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (symbol, strategy, signal_type, price, qty, datetime.now(), sl, tp, 'OPEN'))
    
    conn.commit()
    conn.close()
    print(f"📝 Trade Logged: {signal_type} {qty} {symbol} @ {price}")

def close_trade_in_db(trade_id, exit_price, reason):
    conn = get_connection()
    c = conn.cursor()
    
    # Get trade details
    c.execute('SELECT entry_price, quantity, signal_type, symbol FROM trades WHERE id = ?', (trade_id,))
    entry_price, qty, signal, symbol = c.fetchone()
    
    # Calculate PnL
    if signal == 'BUY':
        pnl = (exit_price - entry_price) * qty
    else: # SELL/SHORT
        pnl = (entry_price - exit_price) * qty
        
    c.execute('''
        UPDATE trades 
        SET status = 'CLOSED', exit_price = ?, exit_time = ?, pnl = ?, exit_reason = ?
        WHERE id = ?
    ''', (exit_price, datetime.now(), pnl, reason, trade_id))
    
    conn.commit()
    conn.close()
    
    # Update Account Balance
    update_balance(pnl)
    print(f"💰 Trade Closed: {symbol} PnL: {pnl:.2f}")
    return pnl

if __name__ == "__main__":
    init_db()
