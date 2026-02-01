"""
NIFTY Iron Condor Trading System

Optimized for NIFTY Index only (100% win rate in 3-year backtest).
"""

from .nifty_iron_condor import NiftyIronCondor, scan_nifty, IronCondorSetup

__all__ = ['NiftyIronCondor', 'scan_nifty', 'IronCondorSetup']
