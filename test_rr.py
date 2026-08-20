import risk_manager

raw_picks = [
    {'symbol': 'JYOTICNC', 'entry': 950.65, 'sl': 931.64, 'target1': 979.17, 'target2': 998.18},
    {'symbol': 'IFCI', 'entry': 81.68, 'sl': 80.05, 'target1': 84.13, 'target2': 85.76},
    {'symbol': 'ACE', 'entry': 1184.80, 'sl': 1161.10, 'target1': 1220.35, 'target2': 1244.05},
    {'symbol': 'WELSPUNLIV', 'entry': 181.24, 'sl': 177.62, 'target1': 186.67, 'target2': 189.92},
    {'symbol': 'ZENTEC', 'entry': 1982.40, 'sl': 1942.75, 'target1': 2041.87, 'target2': 2081.52},
]

for p in raw_picks:
    entry = p['entry']
    sl = p['sl']
    t1 = p['target1']
    reward = abs(t1 - entry)
    risk = abs(entry - sl)
    ratio = reward / risk
    rr_ok = ratio >= 1.5
    pos_size = risk_manager.calculate_position_size(100000, entry, sl)
    print(p['symbol'], "Ratio:", ratio, "RR_OK:", rr_ok, "Pos_Size:", pos_size)
