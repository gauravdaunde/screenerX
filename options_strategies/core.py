
from dataclasses import dataclass
from typing import Dict, List, Optional
import numpy as np
import pandas as pd
import yfinance as yf

# ==========================================
# 1. OPTION PRICING MODEL
# ==========================================
class OptionPricer:
    """
    Estimates option premiums based on Spot, Strike, Time, and VIX.
    Heuristic model since historical option data is unavailable.
    """
    
    @staticmethod
    def get_premium(spot: float, strike: float, type: str, days_to_expiry: int, vix: float) -> float:
        # Baseline: ATM Weekly option is approx 1.0% of Spot at VIX 15
        baseline_vix = 15.0
        vix_factor = vix / baseline_vix
        
        # Time decay (Square root of time rule)
        time_factor = np.sqrt(max(1, days_to_expiry) / 5) # 5 trading days = 1 week
        if days_to_expiry <= 0:
            time_factor = 0.05 

        # Base ATM Premium
        atm_premium = spot * 0.010 * vix_factor * time_factor
        
        # Moneyness (Distance from strike)
        distance_pct = (strike - spot) / spot
        
        # Intrinsic Value
        intrinsic = 0.0
        if type == 'CE':
            intrinsic = max(0, spot - strike)
            if strike > spot: # OTM
                decay_rate = 20 
                extrinsic = atm_premium * np.exp(-abs(distance_pct) * decay_rate)
            else: # ITM
                decay_rate = 20
                extrinsic = atm_premium * np.exp(-abs(distance_pct) * decay_rate)
                
        else: # PE
            intrinsic = max(0, strike - spot)
            if strike < spot: # OTM
                decay_rate = 20
                extrinsic = atm_premium * np.exp(-abs(distance_pct) * decay_rate)
            else: # ITM
                decay_rate = 20
                extrinsic = atm_premium * np.exp(-abs(distance_pct) * decay_rate)
                
        premium = intrinsic + extrinsic
        return max(0.5, premium)

# ==========================================
# 2. CONFIG
# ==========================================
@dataclass
class IndexConfig:
    symbol: str
    ticker: str
    lot_size: int
    wing_dist: int # For IC
    width: int     # For IC/Spreads
    strike_gap: int # Rounding

# ==========================================
# 3. STRATEGIES
# ==========================================
class HedgeStrategy:
    def __init__(self, config: IndexConfig):
        self.config = config
    
    def get_signal(self, row, prev_row) -> Dict:
        raise NotImplementedError

    def create_legs(self, spot: float, vix: float) -> List[Dict]:
        raise NotImplementedError

class IronCondor(HedgeStrategy):
    """Market Neutral Strategy for Side-ways markets."""
    name = "Iron Condor"
    
    def get_signal(self, row, prev_row) -> Dict:
        dist_ema20 = abs(row['close'] - row['ema_20']) / row['close']
        if 40 <= row['rsi'] <= 60 and dist_ema20 < 0.015:
            return {'action': 'ENTER', 'confidence': 80}
        return {'action': 'WAIT'}

    def create_legs(self, spot: float, vix: float) -> List[Dict]:
        gap = self.config.strike_gap
        base = round(spot / gap) * gap
        
        legs = []
        sc_strike = base + self.config.wing_dist
        sp_strike = base - self.config.wing_dist
        lc_strike = sc_strike + self.config.width
        lp_strike = sp_strike - self.config.width
        
        sc_p = OptionPricer.get_premium(spot, sc_strike, 'CE', 5, vix)
        sp_p = OptionPricer.get_premium(spot, sp_strike, 'PE', 5, vix)
        lc_p = OptionPricer.get_premium(spot, lc_strike, 'CE', 5, vix)
        lp_p = OptionPricer.get_premium(spot, lp_strike, 'PE', 5, vix)
        
        legs.append({'strike': sc_strike, 'type': 'CE', 'side': 'SELL', 'price': sc_p})
        legs.append({'strike': sp_strike, 'type': 'PE', 'side': 'SELL', 'price': sp_p})
        legs.append({'strike': lc_strike, 'type': 'CE', 'side': 'BUY', 'price': lc_p})
        legs.append({'strike': lp_strike, 'type': 'PE', 'side': 'BUY', 'price': lp_p})
        return legs

class BullCallSpread(HedgeStrategy):
    """Bullish Directional Strategy."""
    name = "Bull Call Spread"

    def get_signal(self, row, prev_row) -> Dict:
        if row['close'] > row['ema_20'] > row['ema_50'] and 55 < row['rsi'] < 70:
             return {'action': 'ENTER', 'confidence': 80}
        return {'action': 'WAIT'}

    def create_legs(self, spot: float, vix: float) -> List[Dict]:
        gap = self.config.strike_gap
        base = round(spot / gap) * gap
        
        legs = []
        bc_strike = base
        sc_strike = base + self.config.width
        
        bc_p = OptionPricer.get_premium(spot, bc_strike, 'CE', 5, vix)
        sc_p = OptionPricer.get_premium(spot, sc_strike, 'CE', 5, vix)
        
        legs.append({'strike': bc_strike, 'type': 'CE', 'side': 'BUY', 'price': bc_p})
        legs.append({'strike': sc_strike, 'type': 'CE', 'side': 'SELL', 'price': sc_p})
        return legs

class BearPutSpread(HedgeStrategy):
    """Bearish Directional Strategy."""
    name = "Bear Put Spread"

    def get_signal(self, row, prev_row) -> Dict:
        if row['close'] < row['ema_20'] < row['ema_50'] and 30 < row['rsi'] < 45:
             return {'action': 'ENTER', 'confidence': 80}
        return {'action': 'WAIT'}

    def create_legs(self, spot: float, vix: float) -> List[Dict]:
        gap = self.config.strike_gap
        base = round(spot / gap) * gap
        
        legs = []
        bp_strike = base
        sp_strike = base - self.config.width
        
        bp_p = OptionPricer.get_premium(spot, bp_strike, 'PE', 5, vix)
        sp_p = OptionPricer.get_premium(spot, sp_strike, 'PE', 5, vix)
        
        legs.append({'strike': bp_strike, 'type': 'PE', 'side': 'BUY', 'price': bp_p})
        legs.append({'strike': sp_strike, 'type': 'PE', 'side': 'SELL', 'price': sp_p})
        return legs
