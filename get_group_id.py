"""
Helper tool to get your Telegram Group or Channel Chat ID.
How to use:
1. Create your Telegram Group or Channel.
2. Add @sany_trader_bot to the group as an Admin.
3. Send any test message in the group (e.g. "Hello bot").
4. Run this script: python get_group_id.py
"""
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
            print("No new messages found. Please send a message in your group and run again.")
            return
            
        print("=== DETECTED TELEGRAM CHATS ===")
        found_groups = []
        for r in results:
            msg = r.get('message') or r.get('channel_post') or r.get('my_chat_member')
            if msg:
                chat = msg.get('chat', {})
                cid = chat.get('id')
                title = chat.get('title') or chat.get('first_name') or 'Unknown'
                ctype = chat.get('type')
                if cid and (cid, title, ctype) not in found_groups:
                    found_groups.append((cid, title, ctype))
                    print(f"▸ Type: {ctype:<12} | Title: {title:<25} | Chat ID: {cid}")
                    
    except Exception as e:
        print(f"Error checking updates: {e}")

if __name__ == '__main__':
    fetch_group_id()
