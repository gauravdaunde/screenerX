import os
import logging
from typing import Optional
from dhanhq import dhanhq
from dotenv import load_dotenv

# Load env variables if not already loaded
load_dotenv(".env")

# Configure logger
logger = logging.getLogger("dhan_client")

class DhanClient:
    _instance: Optional[dhanhq] = None

    @classmethod
    def get_instance(cls) -> Optional[dhanhq]:
        """
        Returns a singleton instance of the DhanHQ client.
        """
        if cls._instance is None:
            cls._initialize()
        return cls._instance

    @classmethod
    def _initialize(cls):
        """
        Initializes the DhanHQ client with credentials.
        Tries to load from app.core.config first, then falls back to environment variables.
        """
        client_id = None
        access_token = None
        
        # Try importing from config
        try:
            from app.core import config
            client_id = config.DHAN_CLIENT_ID
            access_token = config.DHAN_ACCESS_TOKEN
        except ImportError:
            # Fallback for standalone scripts
            pass

        # If not found or placeholder, try direct env var
        if not client_id or client_id == "YOUR_CLIENT_ID":
            client_id = os.getenv("DHAN_CLIENT_ID")
            
        if not access_token or access_token == "YOUR_ACCESS_TOKEN":
            access_token = os.getenv("DHAN_ACCESS_TOKEN")
        
        # Last resort: Try loading from parent directory .env
        if not client_id or not access_token:
            basedir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
            load_dotenv(os.path.join(basedir, ".env"))
            client_id = os.getenv("DHAN_CLIENT_ID")
            access_token = os.getenv("DHAN_ACCESS_TOKEN")

        if client_id and access_token and client_id != "YOUR_CLIENT_ID":
            try:
                cls._instance = dhanhq(client_id, access_token)
                cls._instance.base_url = "https://api.dhan.co/v2" # Force PROD URL
                logger.info("DhanHQ Client Initialized Successfully")
            except Exception as e:
                logger.error(f"Failed to initialize DhanHQ Client: {e}")
                cls._instance = None
        else:
            logger.warning("DHAN_CLIENT_ID or DHAN_ACCESS_TOKEN not found or is default.")
            cls._instance = None

# Global helper function for easier import
def get_dhan_client() -> Optional[dhanhq]:
    return DhanClient.get_instance()
