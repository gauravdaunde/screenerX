"""
Main Scanner Script.

Runs RSI Divergence and VWAP Breakout strategies on specified symbols.
"""

from backtest_runner import run_backtest
from strategies.rsi_divergence import RSIDivergenceStrategy
from strategies.vwap_breakout import VWAPStrategy

# Symbols to scan
SYMBOLS = [
    "^NSEI",      # Nifty 50
    "^NSEBANK",   # Bank Nifty
    "RELIANCE",
    "TCS",
    "HDFCBANK",
    "INFY",
    "ICICIBANK"
]

STRATEGIES = [
    RSIDivergenceStrategy,
    VWAPStrategy
]

def main():
    print("=" * 50)
    print("  MARKET SCANNER: RSI Divergence + VWAP Breakout")
    print("=" * 50)
    
    for symbol in SYMBOLS:
        print(f"\n--- {symbol} ---")
        for strat_cls in STRATEGIES:
            run_backtest(symbol, strat_cls, output_dir="scan_reports")
    
    print("\n" + "=" * 50)
    print("Scan complete. Reports saved to 'scan_reports/'")
    print("=" * 50)

if __name__ == "__main__":
    main()
