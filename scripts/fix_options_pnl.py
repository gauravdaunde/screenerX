
import sqlite3
import argparse
import sys
import os
from datetime import datetime

# Setup paths
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def fix_swings(db_path):
    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        return

    print(f"🔧 Connecting to {db_path}...")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Find affected trades
    # We look for CLOSED SWING_OPTIONS trades
    # The erroneous ones have huge PnL or specific reason 'TARGET HIT 🎯'
    query = """
        SELECT id, symbol, strategy, quantity, exit_price, pnl 
        FROM trades 
        WHERE (strategy = 'SWING_OPTIONS' OR strategy LIKE 'SWING_OPTIONS%')
          AND status = 'CLOSED' 
          AND exit_reason LIKE '%TARGET HIT%'
    """
    
    c.execute(query)
    rows = c.fetchall()

    if not rows:
        print("✅ No corrupted 'SWING_OPTIONS' closed trades found.")
        conn.close()
        return

    print(f"⚠️ Found {len(rows)} corrupted trades. Fixing...")

    for row in rows:
        trade_id = row['id']
        symbol = row['symbol']
        strategy = row['strategy']
        qty = row['quantity']
        exit_price = row['exit_price']
        pnl = row['pnl']

        # Calculate amount that was wrongly added to wallet
        # close_trade_in_db adds (exit_price * qty) to wallet
        wrong_credit = exit_price * qty
        
        print(f"   • Fixing Trade #{trade_id} {symbol} ({strategy})")
        print(f"     - PnL was: {pnl}")
        print(f"     - Wrong Credit to Revert: ₹{wrong_credit:,.2f}")

        # 1. Update Wallet
        # We need to SUBTRACT the wrong_credit
        c.execute("UPDATE strategy_wallets SET available_balance = available_balance - ?, updated_at = ? WHERE strategy = ?", 
                  (wrong_credit, datetime.now(), strategy))
        
        if c.rowcount == 0:
            print(f"     ⚠️ WARNING: Wallet for '{strategy}' not found or not updated.")

        # 2. Reset Trade to OPEN
        c.execute("""
            UPDATE trades 
            SET status = 'OPEN', 
                exit_price = NULL, 
                exit_time = NULL, 
                pnl = NULL, 
                exit_reason = NULL
            WHERE id = ?
        """, (trade_id,))
        
        print("     ✅ Trade reverted to OPEN.")

    conn.commit()
    conn.close()
    print("🎉 All fixes applied successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fix corrupted PnL for SWING_OPTIONS")
    parser.add_argument("--db", type=str, default="trades.db", help="Path to trades.db")
    args = parser.parse_args()
    
    fix_swings(args.db)
