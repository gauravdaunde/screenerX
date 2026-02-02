import requests
import logging
import config

class AlertBot:
    def __init__(self, token=None, chat_id=None):
        self.token = token or config.TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or config.TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def send_message(self, text):
        """
        Sends a text message to the configured Telegram chat.
        """
        if not self.token or self.token == "YOUR_BOT_TOKEN":
            logging.warning("Telegram Token not set. Sinking alert: " + text)
            return

        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML"
        }
        
        try:
            response = requests.post(url, json=payload)
            if response.status_code != 200:
                logging.error(f"Failed to send Telegram alert: {response.text}")
        except Exception as e:
            logging.error(f"Error sending Telegram alert: {e}")

    def send_validation_alert(self):
        self.send_message("System Started: Stock Screener Online")
