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
# Supports multiple API keys: comma-separated in API_KEYS, or single API_KEY (backwards compatible)
_api_key_single = os.getenv("API_KEY", "")
_api_keys_multi = os.getenv("API_KEYS", "")  # Comma-separated: "key1,key2,key3"

# Combine into a set of valid keys
API_KEYS = set()
if _api_key_single:
    API_KEYS.add(_api_key_single.strip())
if _api_keys_multi:
    API_KEYS.update(k.strip() for k in _api_keys_multi.split(",") if k.strip())

# Backwards compatibility: keep API_KEY for code that uses it
API_KEY = _api_key_single or (list(API_KEYS)[0] if API_KEYS else None)

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
