
import sqlite3
import pandas as pd
from trade_db import init_db, DB_NAME, ensure_wallet_exists, update_strategy_balance

def migrate_wallets():
    print("🚀 Starting Wallet Migration...")
    
    # 1. Ensure Table Exists
    init_db()
    
    conn = sqlite3.connect(DB_NAME)
    
    # 2. Get All Unique Strategies and Trades
    df = pd.read_sql_query("SELECT * FROM trades", conn)
    
    if df.empty:
        print("⚠️ No trades found. Wallets will be initialized on demand.")
        return

    strategies = df['strategy'].unique()
    
    # 3. Reset/seed wallets
    # We want to perform a clean calculation, so we update the wallets to Base 100k first
    c = conn.cursor()
    for strat in strategies:
        if not strat: continue # skip None
        
        # Reset to 100k
        c.execute('''
            INSERT OR REPLACE INTO strategy_wallets (strategy, allocation, available_balance, updated_at)
            VALUES (?, ?, ?, datetime('now'))
        ''', (strat, 100000.0, 100000.0))
        print(f"🔄 Reset wallet for '{strat}' to ₹100,000.00")
        
    conn.commit()
    
    # 4. Replay Trades
    # We need to subtract Entry Cost for ALL trades, and add Exit Value for CLOSED trades
    print("\nCalculations:")
    for index, row in df.iterrows():
        strat = row['strategy']
        if not strat: continue
        
        # Deduct Entry
        entry_cost = row['entry_price'] * row['quantity']
        
        # Add Exit (if closed)
        exit_value = 0.0
        if row['status'] == 'CLOSED' and row['exit_price']:
            exit_value = row['exit_price'] * row['quantity']
            
        # Net change to Cash for this trade
        # Start: 100k
        # Buy: -10k -> Cash 90k
        # Sell: +12k -> Cash 102k
        net_change = exit_value - entry_cost
        
        # Directly update DB for this specific trade replay? 
        # Better to aggregate in memory first for speed, but let's use the DB helper to be safe and consistent
        # Use our own cursor for speed though
        
        c.execute('UPDATE strategy_wallets SET available_balance = available_balance + ? WHERE strategy = ?', (net_change, strat))
        
    conn.commit()
    conn.close()
    
    # 5. Verify
    conn = sqlite3.connect(DB_NAME)
    wallets = pd.read_sql_query("SELECT * FROM strategy_wallets", conn)
    conn.close()
    
    print("\n✅ Migration Complete. Final Balances:")
    print(wallets)

if __name__ == "__main__":
    migrate_wallets()
