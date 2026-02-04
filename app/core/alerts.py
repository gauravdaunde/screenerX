import requests
import logging
from app.core import config

logger = logging.getLogger(__name__)

class AlertBot:
    def __init__(self, token=None, chat_id=None, channel_id=None):
        self.token = token or config.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or config.TELEGRAM_CHAT_ID
        self.channel_id = channel_id or config.TELEGRAM_CHANNEL_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def _send_to_chat(self, chat_id: str, text: str) -> bool:
        """Send a message to a specific chat ID."""
        if not chat_id or chat_id in ["YOUR_CHAT_ID", ""]:
            return False
            
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        
        try:
            response = requests.post(url, json=payload)
            if response.status_code != 200:
                logger.error(f"Failed to send to {chat_id}: {response.text}")
                return False
            return True
        except Exception as e:
            logger.error(f"Error sending to {chat_id}: {e}")
            return False

    def send_message(self, text: str, broadcast: bool = True):
        """
        Sends a text message to configured Telegram destinations.
        
        Args:
            text: Message content
            broadcast: If True, also sends to channel (default). Set False to send only to personal chat.
        """
        if not self.token or self.token == "YOUR_BOT_TOKEN":
            logger.warning("Telegram Token not set. Sinking alert: " + text)
            return

        # Always send to personal chat
        self._send_to_chat(self.chat_id, text)
        
        # Also send to channel if configured and broadcast is enabled
        if broadcast and self.channel_id and self.channel_id not in ["YOUR_CHANNEL_ID", ""]:
            self._send_to_chat(self.channel_id, text)

    def send_to_channel_only(self, text: str):
        """Send message only to the channel, not personal chat."""
        if not self.token or self.token == "YOUR_BOT_TOKEN":
            logger.warning("Telegram Token not set. Sinking alert: " + text)
            return
            
        if self.channel_id and self.channel_id not in ["YOUR_CHANNEL_ID", ""]:
            self._send_to_chat(self.channel_id, text)
        else:
            logger.warning("Channel ID not configured")

    def send_validation_alert(self):
        self.send_message("System Started: Stock Screener Online")

