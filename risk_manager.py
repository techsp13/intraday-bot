import math
import sqlite3
import datetime
from typing import List, Dict, Tuple

try:
    import config
except ImportError:
    # Dummy config for self-test if config module is not found
    class ConfigDummy:
        CAPITAL_BASE = 100000.0
        RISK_PER_TRADE_PCT = 0.01
        MAX_DAILY_LOSS_PCT = 0.03
        MIN_REWARD_RISK_RATIO = 1.5
        DB_PATH = 'data/picks.db'
    config = ConfigDummy()

def calculate_position_size(capital: float, entry: float, sl: float) -> int:
    """
    Calculate the number of shares to trade based on risk parameters.
    """
    risk_amount = capital * config.RISK_PER_TRADE_PCT
    risk_per_share = abs(entry - sl)
    
    if risk_per_share <= 0:
        return 0
        
    qty = math.floor(risk_amount / risk_per_share)
    
    # Cap by max position value: qty * entry should not exceed 20% of capital
    max_position_value = capital * 0.20
    if qty * entry > max_position_value:
        qty = math.floor(max_position_value / entry)
        
    return max(0, qty)

def check_reward_risk(entry: float, sl: float, target1: float) -> bool:
    """
    Check if the potential reward to risk ratio meets the minimum requirement.
    """
    reward = abs(target1 - entry)
    risk = abs(entry - sl)
    
    if risk <= 0:
        return False
        
    return round(reward / risk, 2) >= 1.45

class DailyRiskTracker:
    """
    Tracks daily risk usage using the database log of picks.
    """
    def __init__(self, capital: float = None):
        self.capital = capital if capital is not None else config.CAPITAL_BASE
        
    def is_daily_limit_hit(self, date_str: str) -> Tuple[bool, float]:
        """
        Check if the cumulative loss for the day has reached the maximum allowed limit.
        """
        cumulative_pnl = 0.0
        try:
            with sqlite3.connect(config.DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT SUM(actual_pnl) FROM picks WHERE date = ? AND outcome != 'PENDING'",
                    (date_str,)
                )
                result = cursor.fetchone()
                if result and result[0] is not None:
                    cumulative_pnl = float(result[0])
        except sqlite3.OperationalError:
            # Table might not exist yet, ignoring and assuming 0 pnl
            pass
            
        max_loss = self.capital * config.MAX_DAILY_LOSS_PCT
        is_hit = cumulative_pnl <= -max_loss
        
        return is_hit, cumulative_pnl

def enrich_picks(picks: List[Dict], capital: float) -> List[Dict]:
    """
    Filter and enrich picks with position sizing and risk validation.
    """
    enriched = []
    for pick in picks:
        entry = pick.get('entry', 0.0)
        sl = pick.get('sl', 0.0)
        target1 = pick.get('target1', 0.0)
        
        if not check_reward_risk(entry, sl, target1):
            continue
            
        position_size = calculate_position_size(capital, entry, sl)
        if position_size <= 0:
            continue
            
        risk_per_share = abs(entry - sl)
        risk_amount = position_size * risk_per_share
        
        pick_copy = pick.copy()
        pick_copy['position_size'] = position_size
        pick_copy['risk_amount'] = risk_amount
        
        enriched.append(pick_copy)
        
    return enriched

if __name__ == '__main__':
    # Quick Self-Test
    cap = 100000.0
    entry_price = 100.0
    stop_loss = 98.0
    t1 = 103.0
    
    print(f"Capital: {cap}, Entry: {entry_price}, SL: {stop_loss}, T1: {t1}")
    rr_ok = check_reward_risk(entry_price, stop_loss, t1)
    print(f"RR OK: {rr_ok}")
    
    pos_size = calculate_position_size(cap, entry_price, stop_loss)
    print(f"Position Size: {pos_size}")
    
    picks_to_enrich = [
        {'symbol': 'AAPL', 'entry': 150.0, 'sl': 148.0, 'target1': 153.0}, # RR = 3/2 = 1.5 (passes)
        {'symbol': 'MSFT', 'entry': 250.0, 'sl': 248.0, 'target1': 252.0}  # RR = 2/2 = 1.0 (fails)
    ]
    
    enriched = enrich_picks(picks_to_enrich, cap)
    print(f"Enriched picks: {enriched}")
    
    tracker = DailyRiskTracker(cap)
    today = datetime.datetime.now().strftime('%Y-%m-%d')
    limit_hit, pnl = tracker.is_daily_limit_hit(today)
    print(f"Daily Limit Hit ({today}): {limit_hit}, Cumulative PnL: {pnl}")
