
import os
import json
import requests
import logging
from datetime import datetime
from dotenv import load_dotenv

# Load Environment from root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

# Config
LOG_FILES = [
    os.path.join(BASE_DIR, "screener_api.log"),
    os.path.join(BASE_DIR, "scanner.log"),
    os.path.join(BASE_DIR, "scalper.log"),
    os.path.join(BASE_DIR, "scalper_cron.log")
]
POS_FILE = os.path.join(BASE_DIR, "scripts", "log_positions.json")
KEYWORDS = ["ERROR", "Exception", "Traceback", "failed", "Failure", "CRITICAL"]

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
# destination is the private bot chat
CHAT_ID = os.getenv("TELEGRAM_BOT_CHAT_ID") or os.getenv("TELEGRAM_CHAT_ID")

def send_telegram(message):
    if not TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        # Truncate message if too long for Telegram
        if len(message) > 4000:
            message = message[:3900] + "\n... (truncated)"
        
        requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }, timeout=10)
    except Exception as e:
        print(f"Failed to send telegram: {e}")

def get_positions():
    if os.path.exists(POS_FILE):
        try:
            with open(POS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_positions(pos):
    with open(POS_FILE, 'w') as f:
        json.dump(pos, f)

def monitor():
    positions = get_positions()
    alerts = []

    for log_path in LOG_FILES:
        if not os.path.exists(log_path):
            continue
        
        file_name = os.path.basename(log_path)
        current_size = os.path.getsize(log_path)
        last_pos = positions.get(log_path, 0)

        # Handle log rotation or clearing
        if current_size < last_pos:
            last_pos = 0

        if current_size > last_pos:
            with open(log_path, 'r', errors='ignore') as f:
                f.seek(last_pos)
                new_content = f.read()
                
                # Check for keywords
                found_errors = []
                for line in new_content.splitlines():
                    if any(kw in line for kw in KEYWORDS):
                        found_errors.append(line.strip())
                
                if found_errors:
                    # Take last 5 unique errors to avoid spamming
                    unique_errors = list(dict.fromkeys(found_errors))[-5:]
                    error_msg = "\n".join([f"• `{e}`" for e in unique_errors])
                    alerts.append(f"⚠️ *ERRORS IN {file_name}*\n{error_msg}")

            positions[log_path] = current_size

    if alerts:
        header = f"🚨 *LOG MONITOR ALERT*\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        full_msg = header + "\n\n".join(alerts)
        send_telegram(full_msg)
        print(f"Alerts sent for {len(alerts)} files.")
    else:
        print("No new errors found.")

    save_positions(positions)

if __name__ == "__main__":
    monitor()
