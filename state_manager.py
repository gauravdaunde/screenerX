import sqlite3
import json
import logging
from datetime import datetime

DB_FILE = "trading_state.db"

class StateManager:
    def __init__(self, db_file=DB_FILE):
        self.db_file = db_file
        self.init_db()

    def init_db(self):
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS stock_state (
                symbol TEXT PRIMARY KEY,
                state INTEGER,
                last_updated TIMESTAMP,
                metadata TEXT
            )
        ''')
        conn.commit()
        conn.close()

    def get_state(self, symbol):
        """
        Returns (state, metadata) for a symbol. 
        Returns (0, {}) if not found.
        """
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        c.execute("SELECT state, metadata FROM stock_state WHERE symbol=?", (symbol,))
        row = c.fetchone()
        conn.close()

        if row:
            state = row[0]
            metadata = json.loads(row[1]) if row[1] else {}
            return state, metadata
        return 0, {}

    def update_state(self, symbol, state, metadata=None):
        """
        Updates the state for a symbol.
        """
        conn = sqlite3.connect(self.db_file)
        c = conn.cursor()
        meta_json = json.dumps(metadata) if metadata else "{}"
        
        c.execute('''
            INSERT INTO stock_state (symbol, state, last_updated, metadata)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                state=excluded.state,
                last_updated=excluded.last_updated,
                metadata=excluded.metadata
        ''', (symbol, state, datetime.now(), meta_json))
        
        conn.commit()
        conn.close()
        logging.getLogger(__name__).info(f"Updated {symbol} to State {state}")
