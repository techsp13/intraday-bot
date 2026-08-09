"""
F&O Options Buying Backtest (30 Days)
Applies NIFTY Relative Strength Momentum + Market Regime Filter to Option Buying (Call/Put Options).
Uses Black-Scholes option pricing model for premium & delta simulation.
"""
import pandas as pd
import numpy as np
import yfinance as yf
from scipy.stats import norm
from data_fetcher import load_watchlist

# Black-Scholes Option Call Price
def bs_call_price(S, K, T, r=0.07, sigma=0.15):
    if T <= 0 or sigma <= 0 or S <= 0:
        return max(0.0, S - K)
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)

def run_options_buying_backtest():
    symbols = load_watchlist()[:80]
    all_tickers = symbols + ['^NSEI', '^INDIAVIX']
    print("=== 30-DAY F&O OPTIONS BUYING BACKTEST ===")
    print("Downloading 30-day 5m & 15m intraday market data...")

    df_15m = yf.download(all_tickers, period="30d", interval="15m", progress=False, group_by="ticker")
    df_5m = yf.download(symbols, period="30d", interval="5m", progress=False, group_by="ticker")
    df_daily = yf.download(['^NSEI'], period="60d", interval="1d", progress=False)

    if isinstance(df_daily.columns, pd.MultiIndex):
        df_daily.columns = df_daily.columns.get_level_values(0)
    df_daily.index = df_daily.index.tz_localize(None) if df_daily.index.tz is not None else df_daily.index

    # Regime Filter: Nifty 20 EMA > 50 EMA
    df_daily['Nifty_EMA20'] = df_daily['Close'].ewm(span=20, adjust=False).mean()
    df_daily['Nifty_EMA50'] = df_daily['Close'].ewm(span=50, adjust=False).mean()

    nifty_15m = df_15m['^NSEI'].dropna()
    nifty_15m.index = nifty_15m.index.tz_localize(None) if nifty_15m.index.tz is not None else nifty_15m.index

    capital = 100000.0
    initial_cap = capital
    trades = []
    daily_pnls = {}
    paused_days = 0

    trading_dates = sorted(list(set(nifty_15m.index.date)))

    for t_date in trading_dates:
        prior_daily = df_daily[df_daily.index < pd.Timestamp(t_date)]
        if prior_daily.empty: continue
        last_d = prior_daily.iloc[-1]

        # REGIME PAUSE GATE
        if last_d['Nifty_EMA20'] <= last_d['Nifty_EMA50']:
            paused_days += 1
            continue

        nifty_day = nifty_15m[nifty_15m.index.date == t_date]
        if len(nifty_day) < 2: continue

        nifty_open = nifty_day.iloc[0]['Open']
        nifty_945 = nifty_day.iloc[1]['Close'] if len(nifty_day) > 1 else nifty_open
        nifty_ret = (nifty_945 - nifty_open) / nifty_open * 100.0

        stock_rs = []

        for symbol in symbols:
            try:
                s_15m = df_15m[symbol].dropna() if isinstance(df_15m.columns, pd.MultiIndex) else df_15m
                s_15m.index = s_15m.index.tz_localize(None) if s_15m.index.tz is not None else s_15m.index
                s_day = s_15m[s_15m.index.date == t_date]
                if len(s_day) < 2: continue

                s_open = s_day.iloc[0]['Open']
                s_945 = s_day.iloc[1]['Close']
                s_ret = (s_945 - s_open) / s_open * 100.0
                rs = s_ret - nifty_ret

                if rs > 1.2:
                    stock_rs.append({'symbol': symbol, 'rs': rs})
            except Exception:
                continue

        if not stock_rs: continue

        stock_rs.sort(key=lambda x: x['rs'], reverse=True)
        top_rs_symbols = [x['symbol'] for x in stock_rs[:3]]

        day_pnl = 0.0

        for sym in top_rs_symbols:
            try:
                s_5m = df_5m[sym].dropna() if isinstance(df_5m.columns, pd.MultiIndex) else df_5m
                s_5m.index = s_5m.index.tz_localize(None) if s_5m.index.tz is not None else s_5m.index
                s_5m_day = s_5m[s_5m.index.date == t_date]
                if len(s_5m_day) < 10: continue

                s_5m_day['EMA20'] = s_5m_day['Close'].ewm(span=20, adjust=False).mean()
                s_5m_day['EMA50'] = s_5m_day['Close'].ewm(span=50, adjust=False).mean()

                session = s_5m_day.between_time('09:45', '14:00')

                for dt, row in session.iterrows():
                    close, high, low = row['Close'], row['High'], row['Low']
                    ema20, ema50 = row['EMA20'], row['EMA50']

                    if ema20 > ema50 and abs(low - ema20)/ema20 <= 0.004 and close > ema20:
                        spot_entry = close
                        strike = round(spot_entry / 50.0) * 50.0  # ATM Strike
                        if strike <= 0: strike = spot_entry

                        # BSM Option Premium Calculation
                        time_to_expiry_years = 7.0 / 365.0  # 7 days average to weekly expiry
                        entry_premium = bs_call_price(spot_entry, strike, time_to_expiry_years, r=0.07, sigma=0.18)
                        if entry_premium <= 1.0: entry_premium = spot_entry * 0.015

                        # Option SL (20% premium loss) & Target (35% gain / 60% gain)
                        premium_sl = entry_premium * 0.80
                        premium_t1 = entry_premium * 1.35
                        premium_t2 = entry_premium * 1.60

                        # Sizing: Risk 1% of capital on option buy
                        premium_risk = entry_premium - premium_sl
                        qty = int((capital * 0.01) / premium_risk)
                        if qty <= 0: break

                        rem = s_5m_day.loc[dt:]
                        outcome = 'EXPIRED'
                        exit_spot = rem.iloc[-1]['Close']
                        exit_premium = bs_call_price(exit_spot, strike, (time_to_expiry_years - 0.001), r=0.07, sigma=0.18)

                        for r_dt, r_row in rem.iloc[1:].iterrows():
                            c_high, c_low = r_row['High'], r_row['Low']
                            curr_high_prem = bs_call_price(c_high, strike, time_to_expiry_years, r=0.07, sigma=0.18)
                            curr_low_prem = bs_call_price(c_low, strike, time_to_expiry_years, r=0.07, sigma=0.18)

                            if curr_high_prem >= premium_t1:
                                outcome = 'HIT_T1'
                                exit_premium = premium_t1
                                if curr_high_prem >= premium_t2:
                                    outcome = 'HIT_T2'
                                    exit_premium = premium_t2
                                break
                            elif curr_low_prem <= premium_sl:
                                outcome = 'HIT_SL'
                                exit_premium = premium_sl
                                break

                        pnl = (exit_premium - entry_premium) * qty
                        r_m = pnl / (premium_risk * qty) if (premium_risk * qty) > 0 else 0.0
                        day_pnl += pnl

                        trades.append({
                            'date': str(t_date),
                            'symbol': sym.replace('.NS', ''),
                            'type': 'BUY_CALL (CE)',
                            'strike': strike,
                            'entry_premium': round(entry_premium, 2),
                            'exit_premium': round(exit_premium, 2),
                            'outcome': outcome,
                            'pnl': round(pnl, 2),
                            'r_m': round(r_m, 2)
                        })
                        break
            except Exception:
                continue

        daily_pnls[str(t_date)] = day_pnl

    df_t = pd.DataFrame(trades)
    if df_t.empty:
        print("No F&O option trades triggered.")
        return

    total_trades = len(df_t)
    wins = len(df_t[df_t['outcome'].isin(['HIT_T1', 'HIT_T2'])])
    losses = len(df_t[df_t['outcome'] == 'HIT_SL'])
    exp = len(df_t[df_t['outcome'] == 'EXPIRED'])

    gross_profit = df_t[df_t['pnl'] > 0]['pnl'].sum()
    gross_loss = abs(df_t[df_t['pnl'] < 0]['pnl'].sum())
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.nan
    net_pnl = df_t['pnl'].sum()

    print("\n" + "="*60)
    print("     DETAILED 30-DAY F&O OPTIONS BUYING PERFORMANCE     ")
    print("="*60)
    print(f"Starting Capital:     Rs. {initial_cap:,.2f}")
    print(f"Ending Capital:       Rs. {initial_cap + net_pnl:,.2f}")
    print(f"NET PROFIT / LOSS:    Rs. {net_pnl:+,.2f} ({net_pnl/initial_cap*100:+.2f}%)")
    print(f"Profit Factor:        {profit_factor:.2f}")
    print(f"Average R-Multiple:   {df_t['r_m'].mean():+.2f}R")
    print("-" * 60)
    print(f"Total Option Trades:  {total_trades}")
    print(f"Target Hits (Wins):   {wins} ({(wins/total_trades*100):.1f}%)")
    print(f"Stop Loss Hits:       {losses} ({(losses/total_trades*100):.1f}%)")
    print(f"Expired Exits:        {exp} ({(exp/total_trades*100):.1f}%)")
    print("="*60)

    print("\nSAMPLE RECENT F&O OPTION TRADES:")
    print("-" * 60)
    for idx, row in df_t.tail(10).iterrows():
        print(f"{row['date']} | {row['symbol']:<10} CE | Buy: Rs. {row['entry_premium']:<6.2f} | Exit: Rs. {row['exit_premium']:<6.2f} | {row['outcome']:<8} | P&L: Rs. {row['pnl']:+,.2f}")

if __name__ == '__main__':
    run_options_buying_backtest()
