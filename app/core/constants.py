import sys
import os

try:
    from swing_strategies import NIFTY50
except ImportError:
    sys.path.append(os.getcwd())
    from swing_strategies import NIFTY50

WATCHLIST = ["^NSEI", "^NSEBANK"] + NIFTY50
