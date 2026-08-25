import sqlite3
import datetime

conn = sqlite3.connect('data/picks.db')
c = conn.cursor()
c.execute("SELECT id, date, symbol, direction, entry, sl, target1, target2, position_size, adx FROM picks WHERE date = '2026-08-24' ORDER BY id ASC")
rows = c.fetchall()
print(f"Picks in DB for 2026-08-24: {len(rows)}")
for r in rows:
    print(r)

if not rows:
    print("\nChecking latest entries across all dates in DB:")
    c.execute("SELECT id, date, symbol, direction, entry, sl, target1, target2 FROM picks ORDER BY id DESC LIMIT 10")
    for r in c.fetchall():
        print(r)
