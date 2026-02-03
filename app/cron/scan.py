import sys
import os
from datetime import datetime
from app.services.scanner import get_swing_signals, send_telegram_report
from app.core.constants import WATCHLIST
from app.core.config import logger
from app.core.alerts import AlertBot
from app.core import config

def main():
    logger.info("=" * 60)
    logger.info(f"🚀 RUNNING DAILY SWING SCAN ({datetime.now().strftime('%Y-%m-%d')})")
    logger.info("=" * 60)
    
    # Optional: Health Check Start
    health_bot = AlertBot(token=config.TELEGRAM_HEALTH_BOT_TOKEN)
    start_time = datetime.now()
    try:
        health_bot.send_message(f"🟢 <b>JOB STARTED: Daily Scan</b>\n\n🕒 Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    except:
        pass

    try:
        signals = get_swing_signals(WATCHLIST)
        logger.info("\n\n✅ Scan Complete.")
        
        # Log to console
        if signals:
            logger.info(f"\nFound {len(signals)} signals:")
            for s in signals:
                logger.info(f"  • {s['symbol']} ({s['strategy']}): {s['signal']} (Conf: {s['confidence']:.2f})")
        else:
            logger.info("\nNo signals found.")
            
        # Send to Telegram
        send_telegram_report(signals)
        
        # Health Check Success
        end_time = datetime.now()
        duration = end_time - start_time
        health_bot.send_message(f"✅ <b>JOB SUCCESS: Daily Scan</b>\n\n🕒 End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n⏱️ Duration: {duration}")
        
    except Exception as e:
        logger.error(f"CRITICAL SCAN ERROR: {e}")
        health_bot.send_message(f"🔴 <b>JOB FAILED: Daily Scan</b>\n\nError: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
