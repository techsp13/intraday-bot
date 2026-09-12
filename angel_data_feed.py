import os
import json
import pyotp
from datetime import datetime, timedelta
from dotenv import load_dotenv
from SmartApi import SmartConnect
import pandas as pd

load_dotenv()

_smart_client = None
_token_map = None

def get_angel_client():
    global _smart_client
    if _smart_client is not None:
        return _smart_client
    
    api_key = str(os.getenv('ANGEL_API_KEY', '')).strip()
    client_code = str(os.getenv('ANGEL_CLIENT_CODE', '')).strip()
    mpin = str(os.getenv('ANGEL_MPIN', '')).strip()
    totp_key = str(os.getenv('ANGEL_TOTP_KEY', '')).strip()
    
    if not all([api_key, client_code, mpin, totp_key]):
        raise ValueError('Missing AngelOne credentials in .env')
    
    smart = SmartConnect(api_key=api_key)
    totp = pyotp.TOTP(totp_key).now()
    session = smart.generateSession(client_code, mpin, totp)
    
    if not session.get('status'):
        raise ConnectionError(f"AngelOne Login Failed: {session.get('message')}")
    
    _smart_client = smart
    return _smart_client

def load_instrument_map():
    global _token_map
    if _token_map is not None:
        return _token_map
    
    scrip_file = os.path.join(os.path.dirname(__file__), 'data', 'angel_instruments.json')
    if not os.path.exists(scrip_file):
        import urllib.request
        url = 'https://margincalculator.angelbroking.com/OpenAPI_File/files/OpenAPIScripMaster.json'
        urllib.request.urlretrieve(url, scrip_file)
        
    with open(scrip_file, 'r', encoding='utf-8') as f:
        instruments = json.load(f)
        
    _token_map = {}
    for item in instruments:
        if item.get('exch_seg') == 'NSE' and item.get('symbol', '').endswith('-EQ'):
            base_sym = item['symbol'][:-3]
            _token_map[base_sym] = {
                'token': str(item['token']),
                'tradingsymbol': item['symbol'],
                'name': item.get('name', base_sym)
            }
    return _token_map

def get_candle_df(symbol: str, interval: str = 'ONE_DAY', days_back: int = 45) -> pd.DataFrame:
    """
    Fetch historical candle data from AngelOne SmartAPI.
    Supports NIFTY index ('^NSEI', 'NIFTY') and any NSE equity symbol.
    Returns DataFrame with columns: ['open', 'high', 'low', 'close', 'volume'] indexed by time.
    """
    import pandas as pd
    smart = get_angel_client()
    imap = load_instrument_map()
    clean_sym = symbol.replace('.NS', '').replace('-EQ', '').strip()
    
    if clean_sym in ['^NSEI', 'NIFTY', 'Nifty 50', 'NIFTY50']:
        token = '99926000'
        exch = 'NSE'
    else:
        info = imap.get(clean_sym)
        if not info:
            return pd.DataFrame()
        token = info['token']
        exch = 'NSE'
        
    to_date = datetime.now().strftime('%Y-%m-%d 15:30')
    from_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d 09:15')
    
    try:
        res = smart.getCandleData({
            'exchange': exch,
            'symboltoken': token,
            'interval': interval,
            'fromdate': from_date,
            'todate': to_date
        })
        if res.get('status') and res.get('data'):
            df = pd.DataFrame(res['data'], columns=['time', 'open', 'high', 'low', 'close', 'volume'])
            df['time'] = pd.to_datetime(df['time'])
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            df.set_index('time', inplace=True)
            return df
    except Exception:
        pass
    return pd.DataFrame()

def get_batch_daily_data(symbols: list, days_back: int = 45) -> dict:
    """
    Fetch daily candles for multiple symbols via AngelOne SmartAPI.
    Returns a dict mapping symbol -> DataFrame.
    """
    result = {}
    for s in symbols:
        df = get_candle_df(s, interval='ONE_DAY', days_back=days_back)
        if not df.empty:
            clean_s = s.replace('.NS', '')
            result[clean_s] = df
            result[f"{clean_s}.NS"] = df
    return result

def get_live_quote(symbol: str) -> dict:
    smart = get_angel_client()
    imap = load_instrument_map()
    clean_sym = symbol.replace('.NS', '').replace('-EQ', '')
    
    info = imap.get(clean_sym)
    if not info:
        return {}
        
    token = info['token']
    tsym = info['tradingsymbol']
    
    res = smart.ltpData(exchange='NSE', tradingsymbol=tsym, symboltoken=token)
    if res.get('status') and res.get('data'):
        return res['data']
    return {}

def get_market_depth(symbol: str) -> dict:
    """
    Fetch live Level-2 market depth (5 best bids/asks + total buy/sell quantity) via AngelOne.
    """
    smart = get_angel_client()
    imap = load_instrument_map()
    clean_sym = symbol.replace('.NS', '').replace('-EQ', '')
    
    info = imap.get(clean_sym)
    if not info:
        return {}
        
    token = info['token']
    tsym = info['tradingsymbol']
    
    try:
        res = smart.getMarketData(mode='FULL', exchangeTokens={'NSE': [token]})
        if res.get('status') and res.get('data') and res['data'].get('fetched'):
            item = res['data']['fetched'][0]
            depth = item.get('depth', {})
            tot_buy = float(item.get('totBuyQuan', 0.0))
            tot_sell = float(item.get('totSellQuan', 0.0))
            return {
                'symbol': clean_sym,
                'ltp': float(item.get('ltp', 0.0)),
                'open': float(item.get('open', 0.0)),
                'high': float(item.get('high', 0.0)),
                'low': float(item.get('low', 0.0)),
                'close': float(item.get('close', 0.0)),
                'totBuyQuan': tot_buy,
                'totSellQuan': tot_sell,
                'depth': depth
            }
    except Exception:
        pass
    return {}

if __name__ == '__main__':
    print('Testing AngelOne Real-time Data Feed...')
    q = get_live_quote('RELIANCE')
    print('RELIANCE Live Quote:', q)
    df_n = get_candle_df('^NSEI')
    print('NIFTY Daily Closes from AngelOne (Last 3):')
    print(df_n.tail(3)[['open', 'high', 'low', 'close']])

