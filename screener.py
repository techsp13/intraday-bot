import pandas as pd
import numpy as np
from typing import Tuple, List, Dict, Optional, Union
import config

def calculate_adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.DataFrame:
    """
    Calculate Average Directional Index (ADX).
    Returns DataFrame with columns: plus_di, minus_di, dx, adx
    Uses Wilder's smoothing.
    """
    high_low = high - low
    high_close_prev = (high - close.shift(1)).abs()
    low_close_prev = (low - close.shift(1)).abs()
    tr = pd.concat([high_low, high_close_prev, low_close_prev], axis=1).max(axis=1)
    
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > 0) & (up_move > down_move), up_move, 0.0)
    minus_dm = np.where((down_move > 0) & (down_move > up_move), down_move, 0.0)
    
    tr_smoothed = tr.ewm(alpha=1.0/period, adjust=False).mean()
    plus_dm_smoothed = pd.Series(plus_dm, index=high.index).ewm(alpha=1.0/period, adjust=False).mean()
    minus_dm_smoothed = pd.Series(minus_dm, index=high.index).ewm(alpha=1.0/period, adjust=False).mean()
    
    tr_safe = np.where(tr_smoothed == 0, 1e-9, tr_smoothed)
    plus_di = 100.0 * (plus_dm_smoothed / tr_safe)
    minus_di = 100.0 * (minus_dm_smoothed / tr_safe)
    
    di_sum = plus_di + minus_di
    di_sum_safe = np.where(di_sum == 0, 1e-9, di_sum)
    dx = 100.0 * (np.abs(plus_di - minus_di) / di_sum_safe)
    adx = pd.Series(dx, index=high.index).ewm(alpha=1.0/period, adjust=False).mean()
    
    return pd.DataFrame({'plus_di': plus_di, 'minus_di': minus_di, 'dx': dx, 'adx': adx}, index=high.index)

def calculate_vwap(df: pd.DataFrame) -> pd.Series:
    """
    Intraday VWAP with daily reset. Uses High, Low, Close, Volume columns.
    """
    tp = (df['High'] + df['Low'] + df['Close']) / 3
    pv = tp * df['Volume']
    dates = df.index.date
    cum_pv = pv.groupby(dates).cumsum()
    cum_vol = df['Volume'].groupby(dates).cumsum()
    cum_vol_safe = np.where(cum_vol == 0, 1.0, cum_vol)
    vwap = cum_pv / cum_vol_safe
    # Fallback for zero-volume periods
    no_vol = (cum_vol == 0)
    if no_vol.any():
        fallback_count = tp.groupby(dates).cumcount().add(1)
        cum_tp = tp.groupby(dates).cumsum()
        vwap = pd.Series(vwap, index=df.index).where(~no_vol, cum_tp / fallback_count)
    return pd.Series(vwap, index=df.index)

def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate Average True Range (ATR).
    """
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low - close.shift(1)).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1.0/period, adjust=False).mean()

def get_todays_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filters an intraday DataFrame to only today's candles based on the latest date in the data.
    """
    if df.empty:
        return df
    latest_date = df.index[-1].date()
    return df[df.index.date == latest_date]

def extract_opening_range(intraday_df: pd.DataFrame) -> Optional[Tuple[float, float]]:
    """
    Extracts Opening Range (OR) High and Low.
    Returns (or_high, or_low) or None if insufficient data.
    """
    todays_df = get_todays_data(intraday_df)
    # Filter 09:15 to 09:44
    or_df = todays_df.between_time('09:15', '09:44')
    if or_df.empty:
        return None
    or_high = or_df['High'].max()
    or_low = or_df['Low'].min()
    return or_high, or_low

def detect_breakouts(intraday_df: pd.DataFrame, or_high: float, or_low: float, vwap_series: pd.Series) -> List[Dict]:
    """
    Detect breakouts (Long/Short) using Opening Range and VWAP.
    Scans candles after 09:45 (post-OR candles).
    Returns list of breakout dictionaries.
    """
    breakouts = []
    todays_df = get_todays_data(intraday_df)
    post_or_df = todays_df.between_time('09:45', '15:30')
    
    found_long = False
    found_short = False
    
    # Store OR status for invalidation check
    long_invalidated = False
    short_invalidated = False
    
    for dt, row in post_or_df.iterrows():
        close = row['Close']
        high = row['High']
        low = row['Low']
        vwap = vwap_series.loc[dt]
        
        # Check invalidation if already broken out
        if found_long and close < or_high and close > or_low:
            long_invalidated = True
        if found_short and close < or_high and close > or_low:
            short_invalidated = True
            
        # Long breakout
        if not found_long and not long_invalidated:
            if close > or_high and close > vwap:
                found_long = True
                entry = close
                sl = min(or_low, low)
                risk_r = abs(entry - sl)
                breakouts.append({
                    'direction': 'LONG',
                    'entry': entry,
                    'sl': sl,
                    'target1': entry + 1.5 * risk_r,
                    'target2': entry + 2.5 * risk_r,
                    'risk_r': risk_r,
                    'timestamp': str(dt),
                    'breakout_time': dt.strftime('%H:%M')
                })
                
        # Short breakout
        if not found_short and not short_invalidated:
            if close < or_low and close < vwap:
                found_short = True
                entry = close
                sl = max(or_high, high)
                risk_r = abs(entry - sl)
                breakouts.append({
                    'direction': 'SHORT',
                    'entry': entry,
                    'sl': sl,
                    'target1': entry - 1.5 * risk_r,
                    'target2': entry - 2.5 * risk_r,
                    'risk_r': risk_r,
                    'timestamp': str(dt),
                    'breakout_time': dt.strftime('%H:%M')
                })
                
    return breakouts

def scan_symbol(symbol: str, intraday_df: pd.DataFrame, daily_df: pd.DataFrame, avg_volume: float, avg_turnover: float) -> Optional[List[Dict]]:
    """
    Scans a single symbol for ORB setups and applies scoring.
    """
    # 1. Pre-filter: liquidity
    if avg_turnover < config.MIN_AVG_TURNOVER_CR:
        return None
        
    # 2. Pre-filter: ADX
    if daily_df.empty or len(daily_df) < config.ADX_PERIOD:
        return None
        
    adx_df = calculate_adx(daily_df['High'], daily_df['Low'], daily_df['Close'], period=config.ADX_PERIOD)
    latest_adx_row = adx_df.iloc[-1]
    
    if pd.isna(latest_adx_row['adx']) or latest_adx_row['adx'] < config.ADX_THRESHOLD:
        return None
        
    # 3. Extract Opening Range
    or_tuple = extract_opening_range(intraday_df)
    if or_tuple is None:
        return None
    or_high, or_low = or_tuple
    
    # 4. VWAP
    todays_intraday = get_todays_data(intraday_df)
    if todays_intraday.empty:
        return None
        
    vwap_series = calculate_vwap(todays_intraday)
    
    # 5. Volume ratio
    todays_volume = todays_intraday['Volume'].sum()
    volume_ratio = todays_volume / avg_volume if avg_volume > 0 else 0
    
    # 6. Breakouts
    raw_breakouts = detect_breakouts(todays_intraday, or_high, or_low, vwap_series)
    if not raw_breakouts:
        return None
        
    picks = []
    display_symbol = symbol.replace('.NS', '')
    
    for bo in raw_breakouts:
        # Score calculation
        score = latest_adx_row['adx'] # Base score
        
        if volume_ratio >= config.VOLUME_SURGE_MULTIPLIER:
            score += 10
            
        entry_vwap = vwap_series.loc[pd.to_datetime(bo['timestamp'])]
        if bo['direction'] == 'LONG' and bo['entry'] > entry_vwap:
            score += 5
        elif bo['direction'] == 'SHORT' and bo['entry'] < entry_vwap:
            score += 5
            
        or_range_pct = (or_high - or_low) / or_low * 100
        if or_range_pct > 2.0:
            score -= 5
            
        if bo['direction'] == 'LONG' and latest_adx_row['plus_di'] > latest_adx_row['minus_di']:
            score += 3
        elif bo['direction'] == 'SHORT' and latest_adx_row['minus_di'] > latest_adx_row['plus_di']:
            score += 3
            
        picks.append({
            'symbol': display_symbol,
            'ticker': symbol,
            'direction': bo['direction'],
            'entry': round(bo['entry'], 2),
            'sl': round(bo['sl'], 2),
            'target1': round(bo['target1'], 2),
            'target2': round(bo['target2'], 2),
            'risk_r': round(bo['risk_r'], 2),
            'adx': round(latest_adx_row['adx'], 2),
            'plus_di': round(latest_adx_row['plus_di'], 2),
            'minus_di': round(latest_adx_row['minus_di'], 2),
            'volume_ratio': round(volume_ratio, 2),
            'or_high': round(or_high, 2),
            'or_low': round(or_low, 2),
            'vwap': round(entry_vwap, 2),
            'score': round(score, 1),
            'timestamp': bo['timestamp'],
            'breakout_time': bo['breakout_time']
        })
        
    return picks

def scan_all(intraday_data: Dict[str, pd.DataFrame], daily_data: Dict[str, pd.DataFrame], avg_volumes: Dict[str, float], avg_turnovers: Dict[str, float]) -> List[Dict]:
    """
    Scans all symbols and returns the top MAX_PICKS_PER_RUN picks.
    """
    all_picks = []
    
    for ticker in intraday_data.keys():
        if ticker in daily_data and ticker in avg_volumes and ticker in avg_turnovers:
            picks = scan_symbol(
                symbol=ticker,
                intraday_df=intraday_data[ticker],
                daily_df=daily_data[ticker],
                avg_volume=avg_volumes[ticker],
                avg_turnover=avg_turnovers[ticker]
            )
            if picks:
                all_picks.extend(picks)
                
    # Sort by score descending
    all_picks.sort(key=lambda x: x['score'], reverse=True)
    
    # Return top picks
    max_picks = getattr(config, 'MAX_PICKS_PER_RUN', 5)
    return all_picks[:max_picks]

if __name__ == '__main__':
    print('Screener module loaded. Run via main.py for full pipeline.')
