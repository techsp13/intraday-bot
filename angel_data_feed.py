import os
import json
import pyotp
from datetime import datetime, timedelta
from dotenv import load_dotenv
from SmartApi import SmartConnect

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

if __name__ == '__main__':
    print('Testing AngelOne Real-time Data Feed...')
    q = get_live_quote('RELIANCE')
    print('RELIANCE Live Quote:', q)
