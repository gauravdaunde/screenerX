"""
LIVE Order Test v2 - Uses Regular Order + SL Order (not Bracket).
"""

import os
import requests
from datetime import datetime
from dhanhq import dhanhq

# Load env
env_path = '/Users/gaurav/Documents/code/personal/screener/.env'
with open(env_path, 'r') as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            key, value = line.split('=', 1)
            os.environ[key] = value

DHAN_CLIENT_ID = os.environ.get('DHAN_CLIENT_ID')
DHAN_ACCESS_TOKEN = os.environ.get('DHAN_ACCESS_TOKEN')
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')

# Mock signal
MOCK_SIGNAL = {
    'symbol': 'RELIANCE',
    'security_id': '2885',
    'action': 'BUY',
    'price': 1400.00,
    'sl': 1375.00,
    'tp': 1450.00,
}

CAPITAL = 100000
RISK_PCT = 0.02


def send_telegram(message):
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    try:
        requests.post(url, json={'chat_id': TELEGRAM_CHAT_ID, 'text': message}, timeout=10)
    except Exception:
        pass


def calculate_quantity(entry, sl, capital, risk_pct):
    risk_per_share = abs(entry - sl)
    risk_amount = capital * risk_pct
    qty = int(risk_amount / risk_per_share)
    max_qty = int(capital / entry)
    return min(qty, max_qty)


def place_live_order():
    """Place order using CNC (delivery) with manual SL."""
    
    print("=" * 60)
    print("  🔴 LIVE ORDER TEST (Regular Order)")
    print("=" * 60)
    
    signal = MOCK_SIGNAL
    qty = calculate_quantity(signal['price'], signal['sl'], CAPITAL, RISK_PCT)
    
    print(f"""
    📊 Order Details:
    ─────────────────────────────
    Symbol:         {signal['symbol']}
    Security ID:    {signal['security_id']}
    Action:         {signal['action']}
    Quantity:       {qty}
    Entry Price:    ₹{signal['price']:,.2f}
    Stop Loss:      ₹{signal['sl']:,.2f}
    Target:         ₹{signal['tp']:,.2f}
    Product Type:   CNC (Delivery)
    ─────────────────────────────
    """)
    
    try:
        dhan = dhanhq(DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN)
        print("  ✅ Dhan client connected")
        
        # Place regular LIMIT order (CNC for delivery)
        print("\n  📤 Placing entry order...")
        
        response = dhan.place_order(
            security_id=signal['security_id'],
            exchange_segment=dhan.NSE,
            transaction_type=dhan.BUY,
            quantity=qty,
            order_type=dhan.LIMIT,
            product_type=dhan.CNC,  # Cash & Carry (Delivery)
            price=signal['price'],
            trigger_price=0,
            disclosed_quantity=0,
            validity=dhan.DAY
        )
        
        print(f"\n  📥 Response: {response}")
        
        if isinstance(response, dict):
            status = response.get('status', 'unknown')
            
            if status == 'success':
                order_id = response.get('orderId', response.get('data', {}).get('orderId', 'N/A'))
                print(f"\n  ✅ ENTRY ORDER PLACED!")
                print(f"  🔖 Order ID: {order_id}")
                
                # Now place SL order
                print("\n  📤 Placing Stop-Loss order...")
                
                sl_response = dhan.place_order(
                    security_id=signal['security_id'],
                    exchange_segment=dhan.NSE,
                    transaction_type=dhan.SELL,  # Sell to exit
                    quantity=qty,
                    order_type=dhan.SL,  # Stop Loss order
                    product_type=dhan.CNC,
                    price=signal['sl'] - 1,  # Limit price below trigger
                    trigger_price=signal['sl'],  # SL trigger
                    disclosed_quantity=0,
                    validity=dhan.DAY
                )
                
                print(f"  📥 SL Response: {sl_response}")
                
                sl_order_id = 'N/A'
                if sl_response.get('status') == 'success':
                    sl_order_id = sl_response.get('orderId', 'N/A')
                    print(f"  ✅ SL ORDER PLACED! ID: {sl_order_id}")
                else:
                    print(f"  ⚠️ SL Order issue: {sl_response.get('remarks', 'Unknown')}")
                
                # Send Telegram
                msg = f"""🟢 LIVE ORDERS PLACED!

📈 Symbol: {signal['symbol']}
📊 Action: {signal['action']}
📦 Quantity: {qty}

💰 Entry: ₹{signal['price']:,.2f}
🛑 Stop Loss: ₹{signal['sl']:,.2f}
🎯 Target: ₹{signal['tp']:,.2f}

🔖 Entry Order: {order_id}
🔖 SL Order: {sl_order_id}
⏰ Time: {datetime.now().strftime('%H:%M:%S')}

✅ LIVE - Real orders placed!"""
                send_telegram(msg)
                
            else:
                remarks = response.get('remarks', response.get('data', {}).get('errorMessage', 'Unknown'))
                print(f"\n  ❌ Order Failed: {remarks}")
                send_telegram(f"❌ Order Failed: {remarks}")
                
    except Exception as e:
        print(f"\n  ❌ Exception: {e}")
        send_telegram(f"❌ Order Exception: {e}")


def main():
    print("\n" + "🔴" * 30)
    print("\n⚠️  LIVE TRADING MODE ⚠️")
    print("\n" + "🔴" * 30 + "\n")
    
    now = datetime.now()
    print(f"  ⏰ Time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    
    if now.weekday() >= 5 or now.hour < 9 or now.hour >= 16:
        print("  ⚠️ Market is CLOSED - Order may be queued/rejected\n")
    
    place_live_order()
    
    print("\n" + "=" * 60)
    print("  📋 TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
