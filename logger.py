import sqlite3
import datetime
import os
import yfinance as yf
import pandas as pd
import pytz
from typing import List, Dict, Optional

try:
    import config
except ImportError:
    class ConfigDummy:
        DB_PATH = 'data/picks.db'
    config = ConfigDummy()

def init_db():
    """Initializes the SQLite tables for logging picks and tracking daily summary."""
    db_path = config.DB_PATH
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else '.', exist_ok=True)
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS picks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            entry REAL NOT NULL,
            sl REAL NOT NULL,
            target1 REAL NOT NULL,
            target2 REAL NOT NULL,
            risk_r REAL NOT NULL,
            position_size INTEGER,
            risk_amount REAL,
            adx REAL,
            volume_ratio REAL,
            score INTEGER,
            or_high REAL,
            or_low REAL,
            vwap REAL,
            breakout_time TEXT,
            outcome TEXT DEFAULT 'PENDING',
            actual_exit_price REAL,
            actual_pnl REAL,
            r_multiple REAL,
            notes TEXT
        );
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS daily_summary (
            date TEXT PRIMARY KEY,
            total_picks INTEGER DEFAULT 0,
            triggered INTEGER DEFAULT 0,
            hit_t1 INTEGER DEFAULT 0,
            hit_t2 INTEGER DEFAULT 0,
            hit_sl INTEGER DEFAULT 0,
            no_trigger INTEGER DEFAULT 0,
            expired INTEGER DEFAULT 0,
            win_rate REAL DEFAULT 0.0,
            avg_r_multiple REAL DEFAULT 0.0,
            daily_pnl REAL DEFAULT 0.0,
            capital_after REAL
        );
        """)
        conn.commit()

# Self-initialize on import
init_db()

def _get_ist_now() -> datetime.datetime:
    ist = pytz.timezone('Asia/Kolkata')
    return datetime.datetime.now(pytz.utc).astimezone(ist)

def log_picks(picks: List[Dict]):
    """Insert newly identified picks into the database."""
    now = _get_ist_now()
    date_str = now.strftime('%Y-%m-%d')
    timestamp_str = now.isoformat()
    
    with sqlite3.connect(config.DB_PATH) as conn:
        cursor = conn.cursor()
        for p in picks:
            cursor.execute("""
            INSERT INTO picks (
                date, timestamp, symbol, direction, entry, sl, target1, target2, risk_r,
                position_size, risk_amount, adx, volume_ratio, score, or_high, or_low,
                vwap, breakout_time, outcome
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                date_str,
                timestamp_str,
                p.get('symbol', ''),
                p.get('direction', ''),
                p.get('entry', 0.0),
                p.get('sl', 0.0),
                p.get('target1', 0.0),
                p.get('target2', 0.0),
                p.get('risk_r', 0.0),
                p.get('position_size', 0),
                p.get('risk_amount', 0.0),
                p.get('adx', 0.0),
                p.get('volume_ratio', 0.0),
                p.get('score', 0),
                p.get('or_high', 0.0),
                p.get('or_low', 0.0),
                p.get('vwap', 0.0),
                p.get('breakout_time', ''),
                'PENDING'
            ))
        conn.commit()

def get_today_picks(date_str: Optional[str] = None) -> List[Dict]:
    """Retrieves all picks for a specific date (defaults to today in IST)."""
    if date_str is None:
        date_str = _get_ist_now().strftime('%Y-%m-%d')
        
    with sqlite3.connect(config.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM picks WHERE date = ?", (date_str,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def update_outcome(pick_id: int, outcome: str, exit_price: float, pnl: float, r_multiple: float):
    """Update a specific pick with its finalized execution outcome."""
    with sqlite3.connect(config.DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
        UPDATE picks
        SET outcome = ?, actual_exit_price = ?, actual_pnl = ?, r_multiple = ?
        WHERE id = ?
        """, (outcome, exit_price, pnl, r_multiple, pick_id))
        conn.commit()

def update_outcomes_eod(date_str: str):
    """
    Evaluates end-of-day outcomes for PENDING picks using yfinance 1m data.
    """
    picks = get_today_picks(date_str)
    
    with sqlite3.connect(config.DB_PATH) as conn:
        cursor = conn.cursor()
        
        for pick in picks:
            if pick['outcome'] != 'PENDING':
                continue
                
            symbol = pick['symbol']
            
            # Request 1m data from yfinance for the date
            start_dt = datetime.datetime.strptime(date_str, '%Y-%m-%d')
            end_dt = start_dt + datetime.timedelta(days=1)
            
            # Optional: Add NSE suffix if needed
            yf_symbol = symbol if symbol.endswith('.NS') else f"{symbol}.NS"
            df = yf.download(yf_symbol, start=start_dt, end=end_dt, interval='1m', progress=False)
            
            if df.empty:
                continue
                
            # Filter candles that happened strictly after the breakout_time
            breakout_time_str = pick.get('breakout_time', '09:15:00')
            try:
                df_filtered = df.between_time(breakout_time_str, '15:30:00')
            except Exception:
                df_filtered = df
                
            if df_filtered.empty:
                continue
                
            direction = pick['direction'].upper()
            entry = pick['entry']
            sl = pick['sl']
            target1 = pick['target1']
            target2 = pick['target2']
            pos_size = pick['position_size'] or 0
            risk_r = pick['risk_r'] or abs(entry - sl)
            
            outcome = 'PENDING'
            exit_price = 0.0
            
            # Walk through candles chronologically to determine which level hits first
            for idx, row in df_filtered.iterrows():
                # yfinance format handling for Series/Values
                high = float(row['High'].iloc[0]) if isinstance(row['High'], pd.Series) else float(row['High'])
                low = float(row['Low'].iloc[0]) if isinstance(row['Low'], pd.Series) else float(row['Low'])
                
                if direction == 'LONG':
                    if high >= target1:
                        if high >= target2:
                            outcome = 'HIT_T2'
                            exit_price = target2
                        else:
                            outcome = 'HIT_T1'
                            exit_price = target1
                        break
                    elif low <= sl:
                        outcome = 'HIT_SL'
                        exit_price = sl
                        break
                elif direction == 'SHORT':
                    if low <= target1:
                        if low <= target2:
                            outcome = 'HIT_T2'
                            exit_price = target2
                        else:
                            outcome = 'HIT_T1'
                            exit_price = target1
                        break
                    elif high >= sl:
                        outcome = 'HIT_SL'
                        exit_price = sl
                        break
                        
            # If still PENDING after reading all candles, check if it expired (reached 15:15+)
            if outcome == 'PENDING':
                outcome = 'EXPIRED'
                last_row = df_filtered.iloc[-1]
                close = float(last_row['Close'].iloc[0]) if isinstance(last_row['Close'], pd.Series) else float(last_row['Close'])
                exit_price = close
                
            # Compute actual_pnl and R-Multiple based on outcome exit price
            dir_multiplier = 1 if direction == 'LONG' else -1
            actual_pnl = (exit_price - entry) * pos_size * dir_multiplier
            r_multiple = actual_pnl / (risk_r * pos_size) if (risk_r * pos_size) > 0 else 0.0
            
            # Update the DB record directly
            cursor.execute("""
            UPDATE picks
            SET outcome = ?, actual_exit_price = ?, actual_pnl = ?, r_multiple = ?
            WHERE id = ?
            """, (outcome, exit_price, actual_pnl, r_multiple, pick['id']))
            
        conn.commit()

def compute_daily_summary(date_str: str) -> Dict:
    """Aggregates all picks for the date and upserts the summary."""
    with sqlite3.connect(config.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM picks WHERE date = ?", (date_str,))
        picks = cursor.fetchall()
        
        total = len(picks)
        hit_t1 = sum(1 for p in picks if p['outcome'] == 'HIT_T1')
        hit_t2 = sum(1 for p in picks if p['outcome'] == 'HIT_T2')
        hit_sl = sum(1 for p in picks if p['outcome'] == 'HIT_SL')
        no_trigger = sum(1 for p in picks if p['outcome'] == 'NO_TRIGGER')
        expired = sum(1 for p in picks if p['outcome'] == 'EXPIRED')
        
        triggered = total - no_trigger
        
        wins = hit_t1 + hit_t2
        win_rate = (wins / triggered * 100) if triggered > 0 else 0.0
        
        actual_pnls = [p['actual_pnl'] for p in picks if p['actual_pnl'] is not None]
        r_multiples = [p['r_multiple'] for p in picks if p['r_multiple'] is not None]
        
        daily_pnl = sum(actual_pnls)
        avg_r = sum(r_multiples) / len(r_multiples) if r_multiples else 0.0
        
        cursor.execute("""
        INSERT OR REPLACE INTO daily_summary (
            date, total_picks, triggered, hit_t1, hit_t2, hit_sl, no_trigger, expired,
            win_rate, avg_r_multiple, daily_pnl
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            date_str, total, triggered, hit_t1, hit_t2, hit_sl, no_trigger, expired,
            win_rate, avg_r, daily_pnl
        ))
        conn.commit()
        
        return {
            'date': date_str,
            'total_picks': total,
            'triggered': triggered,
            'hit_t1': hit_t1,
            'hit_t2': hit_t2,
            'hit_sl': hit_sl,
            'no_trigger': no_trigger,
            'expired': expired,
            'win_rate': win_rate,
            'avg_r_multiple': avg_r,
            'daily_pnl': daily_pnl
        }

def get_weekly_summary(num_days: int = 7) -> Dict:
    """Gets the cumulative summary over the last N trading days."""
    with sqlite3.connect(config.DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
        SELECT * FROM daily_summary
        ORDER BY date DESC LIMIT ?
        """, (num_days,))
        
        days = cursor.fetchall()
        
        if not days:
            return {}
            
        total_picks = sum(d['total_picks'] for d in days)
        total_triggered = sum(d['triggered'] for d in days)
        total_wins = sum(d['hit_t1'] + d['hit_t2'] for d in days)
        
        win_rate = (total_wins / total_triggered * 100) if total_triggered > 0 else 0.0
        
        r_mults = [d['avg_r_multiple'] for d in days if d['avg_r_multiple'] != 0.0]
        avg_r = sum(r_mults) / len(r_mults) if r_mults else 0.0
        
        cumulative_pnl = sum(d['daily_pnl'] for d in days)
        
        pnls = [d['daily_pnl'] for d in days]
        best_day = max(pnls) if pnls else 0.0
        worst_day = min(pnls) if pnls else 0.0
        
        return {
            'total_picks': total_picks,
            'win_rate': win_rate,
            'avg_r_multiple': avg_r,
            'cumulative_pnl': cumulative_pnl,
            'best_day': best_day,
            'worst_day': worst_day
        }

def get_cumulative_pnl(date_str: str) -> float:
    """Gets the cumulative actual_pnl for a given date for real-time risk tracking."""
    with sqlite3.connect(config.DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT SUM(actual_pnl) FROM picks WHERE date = ?", (date_str,))
        result = cursor.fetchone()
        if result and result[0] is not None:
            return float(result[0])
        return 0.0

if __name__ == '__main__':
    print("Database initialized successfully at module import.")
