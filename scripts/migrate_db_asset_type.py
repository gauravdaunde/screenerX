
import sqlite3
import sys
import os

# Add project root to path to ensure we can import app modules if needed
sys.path.append(os.getcwd())

from app.core.config import DB_NAME

def migrate_asset_types():
    print(f"🔌 Connecting to database: {DB_NAME}")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    try:
        # Check if column exists (it should, based on previous steps)
        # But if this script is run standalone on an old DB, we might want to ensure it exists
        try:
            c.execute("ALTER TABLE trades ADD COLUMN asset_type TEXT DEFAULT 'STOCK'")
            print("✅ Added 'asset_type' column.")
        except sqlite3.OperationalError:
            print("ℹ️ 'asset_type' column already exists.")

        # Update OPTIONS based on Strategy Name
        # Logic: If strategy name implies options, set asset_type = 'OPTION'
        
        option_keywords = [
            'Iron Condor', 'Bull Call', 'Bear Put', 'Straddle', 'Strangle', 'Butterfly', 
            'Credit Spread', 'Debit Spread', 'Option', 'Call', 'Put'
        ]
        
        # Construct the WHERE clause dynamically or just iterate
        # SQL LIKE is easiest
        
        print("🔄 Updating existing rows...")
        
        count_updated = 0
        for kw in option_keywords:
            c.execute(f"UPDATE trades SET asset_type = 'OPTION' WHERE strategy LIKE '%{kw}%' AND asset_type != 'OPTION'")
            if c.rowcount > 0:
                print(f"   - Updated {c.rowcount} rows matching '{kw}' to OPTION")
                count_updated += c.rowcount
            
        # Also, check entries with symbols that might look like options (e.g. NIFTY25JAN...)
        # Though our system seems to store symbol as 'NIFTY' and strategy as 'Iron Condor'
        
        conn.commit()
        
        if count_updated > 0:
            print(f"🎉 Successfully migrated {count_updated} trade records to 'OPTION' type.")
        else:
            print("🎉 No records needed updating (or no matching Option strategies found).")
            
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_asset_types()
