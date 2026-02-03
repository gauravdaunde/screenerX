import sqlite3
from datetime import datetime

DB_NAME = "trades.db"

def init_db():
    """Initialize the database tables."""
    conn = sqlite3.connect(DB_NAME, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL;") 
    c = conn.cursor()
    
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
    
    # Create Strategy Wallets Table (New)
    c.execute('''
        CREATE TABLE IF NOT EXISTS strategy_wallets (
            strategy TEXT PRIMARY KEY,
            allocation REAL, -- Total Capital Allocated
            available_balance REAL, -- Cash currently available for trading
            updated_at TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ Database initialized (WAL Mode Enabled).")

def get_connection():
    # Helper to get connection with proper timeout
    conn = sqlite3.connect(DB_NAME, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL;") 
    return conn

def ensure_wallet_exists(strategy):
    """Ensure a wallet exists for the strategy. Default 100k if not."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT count(*) FROM strategy_wallets WHERE strategy = ?', (strategy,))
    if c.fetchone()[0] == 0:
        default_capital = 100000.0
        c.execute('''
            INSERT INTO strategy_wallets (strategy, allocation, available_balance, updated_at)
            VALUES (?, ?, ?, ?)
        ''', (strategy, default_capital, default_capital, datetime.now()))
        conn.commit()
        print(f"💼 Created new wallet for '{strategy}' with ₹{default_capital:,.2f}")
    conn.close()

def get_strategy_balance(strategy):
    ensure_wallet_exists(strategy)
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT available_balance FROM strategy_wallets WHERE strategy = ?', (strategy,))
    bal = c.fetchone()[0]
    conn.close()
    return bal

def update_strategy_balance(strategy, amount_change):
    ensure_wallet_exists(strategy)
    conn = get_connection()
    c = conn.cursor()
    
    # Get current
    c.execute('SELECT available_balance FROM strategy_wallets WHERE strategy = ?', (strategy,))
    current = c.fetchone()[0]
    new_bal = current + amount_change
    
    c.execute('UPDATE strategy_wallets SET available_balance = ?, updated_at = ? WHERE strategy = ?', (new_bal, datetime.now(), strategy))
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
    
    # Deduct invested amount from STRATEGY balance
    invested_amount = price * qty
    update_strategy_balance(strategy, -invested_amount)
    
    print(f"📝 Trade Logged: {signal_type} {qty} {symbol} ({strategy}) @ {price} (Invested: ₹{invested_amount:,.2f})")

def close_trade_in_db(trade_id, exit_price, reason):
    conn = get_connection()
    c = conn.cursor()
    
    # Get trade details
    c.execute('SELECT entry_price, quantity, signal_type, symbol, strategy FROM trades WHERE id = ?', (trade_id,))
    row = c.fetchone()
    
    if not row:
        print(f"❌ Trade ID {trade_id} not found.")
        return 0.0
        
    entry_price, qty, signal, symbol, strategy = row
    
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
    
    # Add back the exit value to STRATEGY balance
    exit_value = exit_price * qty
    update_strategy_balance(strategy, exit_value)
    
    print(f"💰 Trade Closed: {symbol} | Exit Value: ₹{exit_value:,.2f} | PnL: ₹{pnl:+,.2f} | Wallet: {strategy}")
    return pnl

if __name__ == "__main__":
    init_db()
