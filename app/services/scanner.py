import logging
import requests
from datetime import datetime
from app.core.config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

# Import strategies and data
# Assuming the app is run from the project root where these packages exist
try:
    from swing_strategies import NIFTY50, fetch_stock_data
    from swing_strategies.supertrend_pivot import scan_stock as scan_supertrend
    from swing_strategies.dispatcher import swing_strategy_dispatcher
except ImportError:
    # Fallback or error handling if running from a different context
    import sys
    import os
    sys.path.append(os.getcwd())
    from swing_strategies import NIFTY50, fetch_stock_data
    from swing_strategies.supertrend_pivot import scan_stock as scan_supertrend
    from swing_strategies.dispatcher import swing_strategy_dispatcher

logger = logging.getLogger(__name__)

def send_telegram_report(signals):
    """Send consolidated report to Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("❌ Telegram credentials missing")
        return

    if not signals:
        message = f"<b>📉 Daily Swing Scan ({datetime.now().strftime('%d-%b')})</b>\n\nNo high-confidence setups found today."
    else:
        message = f"<b>🚀 DAILY SWING SIGNALS ({datetime.now().strftime('%d-%b')})</b>\n\n"
        
        # Group by strategy
        strategies = {}
        for s in signals:
            strat = s['strategy']
            if strat not in strategies:
                strategies[strat] = []
            strategies[strat].append(s)
            
        for strat, items in strategies.items():
            message += f"<b>📌 {strat}</b>\n"
            for s in items:
                emoji = "🟢" if s['signal'] == "BUY" else "🔴"
                conf_icon = "🔥" if s.get('confidence', 0) >= 0.8 else "✨"
                qty = s.get('quantity', 0)
                inv = s.get('invested_value', 0)
                
                message += f"{emoji} <b>{s['symbol']}</b> @ ₹{s['price']:,.2f}\n"
                message += f"   Qty: {qty} | Amt: ₹{inv/1000:.1f}k\n"
                message += f"   SL: ₹{s['stop_loss']:,.2f} | TGT: ₹{s['target']:,.2f}\n"
                message += f"   Reason: {s['reason']} ({int(s.get('confidence',0)*100)}% {conf_icon})\n\n"
            message += "----------------------------\n"
            
        message += "⚠️ <i>Algo-generated. DYOR.</i>"

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    
    try:
        requests.post(url, json=payload)
        logger.info("✅ Telegram report sent!")
    except Exception as e:
        logger.error(f"❌ Failed to send Telegram: {e}")


def get_swing_signals(symbols):
    """
    Run ALL swing strategies on a list of symbols.
    Returns list of signal dictionaries with 100k allocation sizing.
    """
    
    all_signals = []
    total = len(symbols)
    CAPITAL_PER_TRADE = 100000
    
    for idx, symbol in enumerate(symbols):
        # logger.info(f"[{idx+1}/{total}] Scanning {symbol}")
        
        try:
            # Fetch data once (shared)
            df = fetch_stock_data(symbol, period="1y")
            if df.empty or len(df) < 50:
                continue

            # --- 1. EXISTING: SuperTrend Pivot --- 
            st_signal = scan_supertrend(symbol, df)
            if st_signal and st_signal['signal'] in ['BUY', 'SELL']:
                if st_signal['confidence'] >= 0.5:
                    st_signal['strategy'] = "SuperTrend Pivot" # Ensure name
                    # Add sizing
                    price = st_signal['entry_price']
                    qty = int(CAPITAL_PER_TRADE / price) if price > 0 else 0
                    st_signal['quantity'] = qty
                    st_signal['invested_value'] = qty * price
                    all_signals.append(st_signal)

            # --- 2. NEW: Strategy Suite (MACD, BB, EMA, Pullback, Breakout) ---
            # using the dispatcher which picks the BEST of the suite
            suite_signal = swing_strategy_dispatcher(df, symbol)
            
            if suite_signal and suite_signal.get('signal') != 'HOLD':
                 # Avoid duplicates if same strategy logic/name
                 # (Though SuperTrend is distinct from the suite)
                 
                 # Add sizing
                 price = suite_signal.get('entry_price', 0)
                 if price > 0:
                     qty = int(CAPITAL_PER_TRADE / price)
                     suite_signal['quantity'] = qty
                     suite_signal['invested_value'] = qty * price
                     suite_signal['price'] = price # Normalize key if needed
                     all_signals.append(suite_signal)
                
        except Exception as e:
            logger.error(f"Error {symbol}: {e}")
            continue
            
    # Sort by confidence
    all_signals.sort(key=lambda x: x.get('confidence', 0), reverse=True)
    return all_signals
