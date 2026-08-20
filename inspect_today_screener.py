import data_fetcher
import screener
import risk_manager

symbols = data_fetcher.load_watchlist()
print(f"Watchlist size: {len(symbols)}")

intraday_data = data_fetcher.fetch_intraday_data(symbols)
daily_data = data_fetcher.fetch_daily_data(symbols)

avg_volumes = {}
avg_turnovers = {}
for sym in symbols:
    if sym in daily_data and not daily_data[sym].empty:
        avg_volumes[sym] = data_fetcher.compute_avg_daily_volume(daily_data[sym])
        avg_turnovers[sym] = data_fetcher.compute_avg_daily_turnover(daily_data[sym])

raw_picks = screener.scan_all(intraday_data, daily_data, avg_volumes, avg_turnovers)
print(f"\nRaw screener candidates (RS >= +2.0%): {len(raw_picks)}")
for p in raw_picks:
    print(f"  {p['symbol']:<12} | RS Outperformance: +{p['adx']:.2f}% | Entry: Rs.{p['entry']:.2f}")

sized_picks = risk_manager.enrich_picks(raw_picks, 100000)
print(f"\nAfter Risk & Max-Allocation Filters: {len(sized_picks)} picks")
for p in sized_picks:
    print(f"  -> {p['symbol']:<12} | Qty: {p['position_size']} shares | Risk: Rs.{p['risk_amount']:.0f} | Alloc: Rs.{p['entry']*p['position_size']:,.0f}")
