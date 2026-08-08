import os
import time
import logging
import datetime
from pathlib import Path
import requests
import pandas as pd
import numpy as np
import yfinance as yf

# Import config (assuming it exists in the same directory)
try:
    import config
except ImportError:
    logging.warning("config.py not found. Using default configurations.")
    class config:
        DATA_DIR = "data"
        WATCHLIST_CACHE = "data/watchlist.csv"
        WATCHLIST_SOURCE = "NIFTY500"

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def strip_timezone(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Convert a timezone-aware DatetimeIndex to timezone-naive."""
    if index.tz is not None:
        return index.tz_localize(None)
    return index

def load_watchlist() -> list[str]:
    """
    Load the NIFTY 500 (or specified) watchlist from cache or download it.
    Returns a list of yfinance-compatible symbols (e.g. 'RELIANCE.NS').
    """
    Path(config.DATA_DIR).mkdir(parents=True, exist_ok=True)
    cache_path = Path(config.WATCHLIST_CACHE)
    
    download_needed = True
    if cache_path.exists():
        mtime = cache_path.stat().st_mtime
        age_days = (time.time() - mtime) / (24 * 3600)
        if age_days < 30:
            download_needed = False
            logger.info(f"Using cached watchlist ({age_days:.1f} days old).")
        else:
            logger.info("Watchlist cache is older than 30 days. Re-downloading.")

    if download_needed:
        url = "https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv"
        if hasattr(config, 'WATCHLIST_SOURCE') and config.WATCHLIST_SOURCE == "NIFTY200":
            url = "https://www.niftyindices.com/IndexConstituent/ind_nifty200list.csv"
            
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            with open(cache_path, 'wb') as f:
                f.write(response.content)
            logger.info(f"Successfully downloaded watchlist from {url}")
        except Exception as e:
            logger.error(f"Failed to download watchlist: {e}")
            if cache_path.exists():
                logger.info("Falling back to existing cached watchlist.")
            else:
                logger.error("No cached watchlist available.")
                return []

    try:
        df = pd.read_csv(cache_path)
        # Handle variations in column names like 'Symbol' or 'Symbol '
        symbol_col = next((col for col in df.columns if 'Symbol' in col), None)
        
        if not symbol_col:
            logger.error(f"Could not find Symbol column in watchlist. Columns: {df.columns.tolist()}")
            return []
            
        # Clean symbols and append .NS
        symbols = df[symbol_col].astype(str).str.strip().tolist()
        
        # M&M becomes M&M.NS on yfinance, remove any weird formatting if needed.
        symbols = [f"{sym}.NS" for sym in symbols if sym]
        return symbols
    except Exception as e:
        logger.error(f"Error reading watchlist CSV: {e}")
        return []

def _process_yf_download(df: pd.DataFrame, symbols: list[str], cache_prefix: str) -> dict[str, pd.DataFrame]:
    """Helper to process yfinance download DataFrame, whether single or multi-index."""
    result = {}
    if df.empty:
        return result

    if isinstance(df.columns, pd.MultiIndex):
        # MultiIndex columns: Level 0 is Price (Open, High...), Level 1 is Ticker
        for sym in symbols:
            try:
                sym_df = df.xs(sym, level=1, axis=1).dropna(how='all')
                if not sym_df.empty:
                    # Ensure standard column names
                    sym_df.columns = [str(c).title() for c in sym_df.columns]
                    sym_df.index = strip_timezone(pd.DatetimeIndex(sym_df.index))
                    result[sym] = sym_df
                    cache_file = Path(config.DATA_DIR) / f"{cache_prefix}_{sym}.parquet"
                    sym_df.to_parquet(cache_file)
            except Exception as e:
                logger.warning(f"Error processing symbol {sym}: {e}")
    else:
        # Single symbol case
        if len(symbols) == 1:
            sym = symbols[0]
            df = df.dropna(how='all').copy()
            if not df.empty:
                df.columns = [str(c).title() for c in df.columns]
                df.index = strip_timezone(pd.DatetimeIndex(df.index))
                result[sym] = df
                cache_file = Path(config.DATA_DIR) / f"{cache_prefix}_{sym}.parquet"
                df.to_parquet(cache_file)
                
    return result

def fetch_intraday_data(symbols: list[str], period: str = '5d') -> dict[str, pd.DataFrame]:
    """
    Fetch 5-minute intraday data for given symbols.
    Caches the results locally.
    """
    Path(config.DATA_DIR).mkdir(parents=True, exist_ok=True)
    all_data = {}
    
    chunk_size = 50
    chunks = [symbols[i:i + chunk_size] for i in range(0, len(symbols), chunk_size)]
    
    for i, chunk in enumerate(chunks):
        logger.info(f"Fetching intraday chunk {i+1}/{len(chunks)} ({len(chunk)} symbols)...")
        try:
            df = yf.download(
                tickers=chunk,
                period=period,
                interval='5m',
                progress=False,
                ignore_tz=True,
                group_by='column' 
            )
            processed = _process_yf_download(df, chunk, "cache_5m")
            all_data.update(processed)
        except Exception as e:
            logger.error(f"Error fetching intraday data for chunk {i+1}: {e}")
            
        if i < len(chunks) - 1:
            time.sleep(2)
            
    return all_data

def fetch_daily_data(symbols: list[str], period: str = '25d') -> dict[str, pd.DataFrame]:
    """
    Fetch daily data for given symbols.
    Caches the results locally.
    """
    Path(config.DATA_DIR).mkdir(parents=True, exist_ok=True)
    all_data = {}
    
    chunk_size = 50
    chunks = [symbols[i:i + chunk_size] for i in range(0, len(symbols), chunk_size)]
    
    for i, chunk in enumerate(chunks):
        logger.info(f"Fetching daily chunk {i+1}/{len(chunks)} ({len(chunk)} symbols)...")
        try:
            df = yf.download(
                tickers=chunk,
                period=period,
                interval='1d',
                progress=False,
                ignore_tz=True,
                group_by='column'
            )
            processed = _process_yf_download(df, chunk, "cache_1d")
            all_data.update(processed)
        except Exception as e:
            logger.error(f"Error fetching daily data for chunk {i+1}: {e}")
            
        if i < len(chunks) - 1:
            time.sleep(2)
            
    return all_data

def compute_avg_daily_volume(daily_df: pd.DataFrame, lookback: int = 20) -> float:
    """Compute average daily volume over the specified lookback period."""
    if daily_df.empty or 'Volume' not in daily_df.columns:
        return 0.0
    return float(daily_df['Volume'].tail(lookback).mean())

def compute_avg_daily_turnover(daily_df: pd.DataFrame, lookback: int = 20) -> float:
    """
    Compute average daily turnover (Close * Volume) over the lookback period.
    Returns the turnover in Crores (divided by 1e7).
    """
    if daily_df.empty or 'Volume' not in daily_df.columns or 'Close' not in daily_df.columns:
        return 0.0
    
    recent_df = daily_df.tail(lookback)
    turnover = recent_df['Close'] * recent_df['Volume']
    
    # 1 Crore = 10,000,000
    avg_turnover_cr = turnover.mean() / 1e7
    return float(avg_turnover_cr)


if __name__ == '__main__':
    symbols = load_watchlist()
    print(f"Loaded {len(symbols)} symbols")
    
    if symbols:
        # Quick test with 5 symbols
        test_symbols = symbols[:5]
        print(f"Testing with: {test_symbols}")
        
        intraday = fetch_intraday_data(test_symbols)
        print(f"Fetched intraday data for {len(intraday)} symbols")
        
        daily = fetch_daily_data(test_symbols)
        print(f"Fetched daily data for {len(daily)} symbols")
        
        for sym in test_symbols:
            if sym in daily:
                vol = compute_avg_daily_volume(daily[sym])
                turnover = compute_avg_daily_turnover(daily[sym])
                print(f"{sym}: avg_vol={vol:,.0f}, avg_turnover=₹{turnover:.1f}cr")
