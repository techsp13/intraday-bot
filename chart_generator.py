"""
High-Precision Zoomed Intraday Candlestick Chart Generator
Renders zoomed-in 5m intraday candles with bold Entry, SL, T1, T2 level lines and crisp callouts.
"""
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

import pandas as pd
import yfinance as yf

def generate_candlestick_chart(pick: dict) -> str:
    """
    Generates a zoomed-in, high-definition 5m intraday dark mode candlestick chart.
    """
    if not HAS_MATPLOTLIB:
        print("Warning: matplotlib not installed. Skipping chart generation.")
        return ""
    symbol = pick.get('symbol', 'STOCK')
    ticker = pick.get('ticker', f"{symbol}.NS")
    entry = pick.get('entry', 0.0)
    sl = pick.get('sl', 0.0)
    target1 = pick.get('target1', 0.0)
    target2 = pick.get('target2', 0.0)

    try:
        df = yf.download(ticker, period="3d", interval="5m", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna(subset=['Open', 'High', 'Low', 'Close'])
        
        if not df.empty:
            df.index = df.index.tz_localize(None) if df.index.tz is not None else df.index
            last_date = df.index.date[-1]
            df = df[df.index.date == last_date]
            # Zoomed focus: Last 35 candles (~3 hours of trading session)
            if len(df) > 35:
                df = df.tail(35)
    except Exception as e:
        print(f"Error downloading 5m intraday chart data for {symbol}: {e}")
        return ""

    if df.empty:
        return ""

    # Create Dark Mode Plot
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(11, 6.5), dpi=180)
    fig.patch.set_facecolor('#0E1621')
    ax.set_facecolor('#17212B')

    width = 0.70  # Bolder, zoomed candles

    # Draw Zoomed Candlesticks
    for i, (dt, row) in enumerate(df.iterrows()):
        color = '#00E676' if row['Close'] >= row['Open'] else '#FF5252'
        # Wick
        ax.plot([i, i], [row['Low'], row['High']], color=color, linewidth=1.8)
        # Body
        body_bottom = min(row['Open'], row['Close'])
        body_height = max(abs(row['Close'] - row['Open']), 0.08)
        rect = plt.Rectangle((i - width/2, body_bottom), width, body_height, facecolor=color, edgecolor=color, alpha=0.95)
        ax.add_patch(rect)

    # X-axis 5m Time Labels
    step = max(1, len(df) // 8)
    indices = list(range(0, len(df), step))
    time_labels = [df.index[i].strftime('%I:%M %p') for i in indices]
    ax.set_xticks(indices)
    ax.set_xticklabels(time_labels, rotation=25, ha='right', fontsize=10, color='#B0BEC5', fontweight='bold')

    # Zoom Y-axis limits tightly around levels
    all_prices = list(df['Low']) + list(df['High']) + [entry, sl, target1, target2]
    min_price = min(all_prices) * 0.995
    max_price = max(all_prices) * 1.005
    ax.set_ylim(min_price, max_price)

    x_min, x_max = -0.5, len(df) - 0.5
    ax.set_xlim(x_min, x_max)

    # Entry Line (Bright Blue)
    ax.hlines(y=entry, xmin=x_min, xmax=x_max, colors='#29B6F6', linestyles='--', linewidth=2.0, label=f'ENTRY: Rs. {entry:,.2f}')
    # SL Line (Bright Red)
    ax.hlines(y=sl, xmin=x_min, xmax=x_max, colors='#FF1744', linestyles='--', linewidth=2.0, label=f'SL: Rs. {sl:,.2f} (-2.0%)')
    # Target 1 Line (Light Green)
    ax.hlines(y=target1, xmin=x_min, xmax=x_max, colors='#00E676', linestyles='-.', linewidth=2.0, label=f'TARGET 1: Rs. {target1:,.2f} (+3.0%)')
    # Target 2 Line (Bright Lime Green)
    ax.hlines(y=target2, xmin=x_min, xmax=x_max, colors='#C0CA33', linestyles='-', linewidth=2.2, label=f'TARGET 2: Rs. {target2:,.2f} (+5.0%)')

    # Title & Axis Labels
    trade_date_str = df.index[-1].strftime('%d-%b-%Y')
    ax.set_title(f"🚀 INTRADAY BREAKOUT (ZOOMED): {symbol} — {trade_date_str}", fontsize=14, fontweight='bold', color='#FFFFFF', pad=14)
    ax.set_ylabel("Price (Rs.)", fontsize=11, color='#B0BEC5', fontweight='bold')
    ax.grid(True, linestyle=':', alpha=0.3, color='#FFFFFF')

    # Right Axis Level Annotations
    right_x = len(df) - 0.1
    ax.annotate(f" T2: Rs. {target2:,.2f}", xy=(right_x, target2), fontsize=10, fontweight='bold', color='#C0CA33', verticalalignment='center')
    ax.annotate(f" T1: Rs. {target1:,.2f}", xy=(right_x, target1), fontsize=10, fontweight='bold', color='#00E676', verticalalignment='center')
    ax.annotate(f" ENTRY: Rs. {entry:,.2f}", xy=(right_x, entry), fontsize=10, fontweight='bold', color='#29B6F6', verticalalignment='center')
    ax.annotate(f" SL: Rs. {sl:,.2f}", xy=(right_x, sl), fontsize=10, fontweight='bold', color='#FF1744', verticalalignment='center')

    ax.legend(loc='upper left', frameon=True, facecolor='#17212B', edgecolor='#2B5278', fontsize=9.5)

    plt.tight_layout()

    # Save PNG image
    os.makedirs('charts', exist_ok=True)
    chart_file = os.path.join('charts', f"chart_{symbol}.png")
    plt.savefig(chart_file, facecolor=fig.get_facecolor(), bbox_inches='tight')
    plt.close()

    print(f"Zoomed high-definition 5m chart generated: {chart_file}")
    return chart_file

if __name__ == '__main__':
    sample_pick = {
        'symbol': 'FINCABLES',
        'ticker': 'FINCABLES.NS',
        'entry': 1280.05,
        'sl': 1254.45,
        'target1': 1318.45,
        'target2': 1344.05
    }
    generate_candlestick_chart(sample_pick)
