import sys
import io
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

import urllib.request
import json
import config

def fetch_group_id():
    token = getattr(config, 'TELEGRAM_BOT_TOKEN', '8516916612:AAHW5wSNcp5K82lMhBpiRMSWLy-LHw1-Wrc')
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            
        results = data.get('result', [])
        if not results:
            print("No updates found.")
            return
            
        print("=== DETECTED TELEGRAM CHATS ===")
        found_groups = []
        for r in results:
            msg = r.get('message') or r.get('channel_post') or r.get('my_chat_member')
            if msg:
                chat = msg.get('chat', {})
                cid = str(chat.get('id'))
                title = chat.get('title') or chat.get('first_name') or 'Unknown'
                ctype = chat.get('type')
                if cid and (cid, title, ctype) not in found_groups:
                    found_groups.append((cid, title, ctype))
                    print(f"Type: {ctype:<12} | Title: {title:<25} | Chat ID: {cid}")
                    
    except Exception as e:
        print(f"Error checking updates: {e}")

if __name__ == '__main__':
    fetch_group_id()
