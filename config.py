import os
from dotenv import load_dotenv

load_dotenv()

# DhanHQ Credentials
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "YOUR_CLIENT_ID")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "YOUR_ACCESS_TOKEN")

# Telegram Credentials
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_HEALTH_BOT_TOKEN = os.getenv("TELEGRAM_HEALTH_BOT_TOKEN", "YOUR_HEALTH_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")

# Trading Config
SYMBOLS = ["NIFTY", "BANKNIFTY", "RELIANCE", "TCS", "INFY"]  # Example symbols
TIMEFRAME_HTF = "60"  # 1 Hour
TIMEFRAME_LTF = "5"   # 5 Minute
