
import sys
import os

try:
    from swing_strategies import NIFTY50
except ImportError:
    # Try adding root to path if running from subdir
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    if root_dir not in sys.path:
        sys.path.append(root_dir)
    try:
        from swing_strategies import NIFTY50
    except ImportError:
        NIFTY50 = [] # Fallback

WATCHLIST = ["^NSEI", "^NSEBANK"] + NIFTY50

# NSE Equity Security IDs for Dhan API (NIFTY 50)
SECURITY_IDS = {
    "RELIANCE": "2885",
    "TCS": "11536",
    "HDFCBANK": "1333",
    "ICICIBANK": "4963",
    "INFY": "1594",
    "SBIN": "3045",
    "ITC": "1660",
    "BHARTIARTL": "10604",
    "KOTAKBANK": "1922",
    "LT": "11483",
    "HCLTECH": "700",
    "AXISBANK": "5900",
    "ASIANPAINT": "236",
    "MARUTI": "10999",
    "SUNPHARMA": "3351",
    "TITAN": "3506",
    "ULTRACEMCO": "11532",
    "BAJFINANCE": "317",
    "WIPRO": "3787",
    "NESTLEIND": "17963",
    "TATAMOTORS": "3456",
    "M&M": "2031",
    "NTPC": "11630",
    "POWERGRID": "14977",
    "TECHM": "13538",
    "TATASTEEL": "3499",
    "ADANIENT": "25",
    "ADANIPORTS": "15083",
    "JSWSTEEL": "11723",
    "ONGC": "2475",
    "COALINDIA": "20374",
    "BAJAJFINSV": "16675",
    "HDFCLIFE": "467",
    "DRREDDY": "881",
    "DIVISLAB": "10940",
    "GRASIM": "1232",
    "CIPLA": "694",
    "APOLLOHOSP": "157",
    "BRITANNIA": "547",
    "EICHERMOT": "910",
    "SBILIFE": "21808",
    "BPCL": "526",
    "TATACONSUM": "3432",
    "INDUSINDBK": "5258",
    "HINDALCO": "1363",
    "HEROMOTOCO": "1348",
    "UPL": "11287",
    "LTIM": "17818",
    "BEL": "383",
    "TRENT": "1964",
    "HINDUNILVR": "1330" 
}

# Indices
INDEX_IDS = {
    "NIFTY": "13",
    "BANKNIFTY": "25"
}
