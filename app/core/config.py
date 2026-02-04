import os
import logging
from dotenv import load_dotenv

# Load env variables
basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
load_dotenv(os.path.join(basedir, ".env"))

# --- LOGGING CONFIG ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("screener_api.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("screener")

# --- AUTH CONFIG ---
API_KEY = os.getenv("API_KEY")

# --- TELEGRAM CONFIG ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_HEALTH_BOT_TOKEN = os.getenv("TELEGRAM_HEALTH_BOT_TOKEN", "YOUR_HEALTH_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID", "")  # Optional: Channel for broadcasting alerts to all subscribers

# --- DHAN CONFIG ---
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID", "YOUR_CLIENT_ID")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN", "YOUR_ACCESS_TOKEN")

# --- DATABASE CONFIG ---
DB_NAME = "trades.db"
