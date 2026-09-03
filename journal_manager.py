"""
Trade Journal Manager for Sanket's Intraday Trading System.
Tracks daily manual trade executions, realized P&L, running Demat balance, and progress towards ₹1 Crore.
"""
import os
import json
from datetime import datetime

JOURNAL_FILE = os.path.join(os.path.dirname(__file__), 'data', 'trade_journal.json')
INITIAL_BALANCE = 6800.0
TARGET_GOAL = 10000000.0 # ₹1 Crore

def load_journal():
    if not os.path.exists(JOURNAL_FILE):
        return {
            'initial_balance': INITIAL_BALANCE,
            'current_balance': INITIAL_BALANCE,
            'target_goal': TARGET_GOAL,
            'trades': []
        }
    try:
        with open(JOURNAL_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {
            'initial_balance': INITIAL_BALANCE,
            'current_balance': INITIAL_BALANCE,
            'target_goal': TARGET_GOAL,
            'trades': []
        }

def save_journal(data):
    os.makedirs(os.path.dirname(JOURNAL_FILE), exist_ok=True)
    with open(JOURNAL_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def log_trade(date_str, stock, direction, shares, entry, exit_p, pnl, notes=""):
    data = load_journal()
    trades = data.get('trades', [])
    
    current_bal = data.get('current_balance', INITIAL_BALANCE) + pnl
    data['current_balance'] = round(current_bal, 2)
    
    trade_entry = {
        'id': len(trades) + 1,
        'date': date_str,
        'stock': stock.upper(),
        'direction': direction.upper(),
        'shares': int(shares),
        'entry': float(entry),
        'exit': float(exit_p),
        'pnl': round(float(pnl), 2),
        'balance_after': round(current_bal, 2),
        'notes': notes
    }
    
    trades.append(trade_entry)
    data['trades'] = trades
    save_journal(data)
    print(f"Logged trade: {stock} ({direction}) | PnL: Rs.{pnl:,.2f} | Balance: Rs.{current_bal:,.2f}")
    return trade_entry

def clear_journal(starting_balance=6800.0):
    data = {
        'initial_balance': float(starting_balance),
        'current_balance': float(starting_balance),
        'target_goal': TARGET_GOAL,
        'trades': []
    }
    save_journal(data)
    print(f"Trade journal reset to clean starting state with Rs.{starting_balance:,.2f} balance.")

def get_stats():
    data = load_journal()
    trades = data.get('trades', [])
    init_bal = data.get('initial_balance', INITIAL_BALANCE)
    curr_bal = data.get('current_balance', INITIAL_BALANCE)
    
    total_pnl = curr_bal - init_bal
    roi_pct = (total_pnl / init_bal) * 100.0 if init_bal > 0 else 0
    
    wins = [t for t in trades if t.get('pnl', 0) > 0]
    losses = [t for t in trades if t.get('pnl', 0) < 0]
    win_rate = (len(wins) / len(trades) * 100.0) if trades else 0.0
    
    progress_pct = (curr_bal / TARGET_GOAL) * 100.0
    
    return {
        'initial_balance': init_bal,
        'current_balance': curr_bal,
        'total_pnl': total_pnl,
        'roi_pct': roi_pct,
        'total_trades': len(trades),
        'wins': len(wins),
        'losses': len(losses),
        'win_rate': win_rate,
        'progress_pct': progress_pct,
        'target_goal': TARGET_GOAL
    }

if __name__ == '__main__':
    # Add sample test entries
    clear_journal(6800.0)
    log_trade("2026-09-02", "NSLNISP", "LONG", 149, 45.61, 47.19, 217.89, "Target 1 Hit (+3.0%)")
    log_trade("2026-09-03", "IFCI", "LONG", 69, 98.32, 101.28, 204.24, "Target 1 Hit (+3.0%)")
    log_trade("2026-09-03", "ZEEL", "SHORT", 75, 90.57, 92.38, -135.75, "Stop Loss Hit (-2.0%)")
    log_trade("2026-09-03", "ENGINERSIN", "LONG", 24, 276.60, 284.90, 199.20, "Target 1 Hit (+3.0%)")
    print("\nSAMPLE STATS:", get_stats())
