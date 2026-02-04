import logging
from datetime import datetime
from app.core.alerts import AlertBot

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

# Initialize alert bot for broadcasting
alert_bot = AlertBot()

def send_telegram_report(signals):
    """Send consolidated report to Telegram (personal chat + channel)."""
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
                # Handle both 'price' and 'entry_price' keys
                price = s.get('price', s.get('entry_price', 0))
                sl = s.get('stop_loss', 0)
                tp = s.get('target', 0)
                
                message += f"{emoji} <b>{s['symbol']}</b> @ ₹{price:,.2f}\n"
                message += f"   Qty: {qty} | Amt: ₹{inv/1000:.1f}k\n"
                message += f"   SL: ₹{sl:,.2f} | TGT: ₹{tp:,.2f}\n"
                message += f"   Reason: {s.get('reason', 'N/A')} ({int(s.get('confidence',0)*100)}% {conf_icon})\n\n"
            message += "----------------------------\n"
            
        message += "⚠️ <i>Algo-generated. DYOR.</i>"

    # Send to both personal chat and channel
    alert_bot.send_message(message, broadcast=True)
    logger.info("✅ Telegram report sent!")


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
                 # Normalize 'strategy_name' to 'strategy' for consistency
                 if 'strategy_name' in suite_signal and 'strategy' not in suite_signal:
                     suite_signal['strategy'] = suite_signal['strategy_name']
                 
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
