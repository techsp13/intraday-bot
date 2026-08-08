import os
from dotenv import load_dotenv
load_dotenv()

# ── Capital & Risk ─────────────────────────────────────
CAPITAL_BASE = float(os.getenv("CAPITAL_BASE", "100000"))
RISK_PER_TRADE_PCT = 0.01          # 1% of capital per trade
MAX_DAILY_LOSS_PCT = 0.03          # 3% of capital daily limit
MIN_REWARD_RISK_RATIO = 1.5        # Reject picks below 1.5R
MAX_PICKS_PER_RUN = 5              # Top N picks to send

# ── Screener Parameters ───────────────────────────────
OR_START = "09:15"                  # Opening Range start
OR_END = "09:45"                    # Opening Range end (6x 5m candles)
OR_CANDLES = 6                      # Number of 5m candles in OR
ADX_PERIOD = 14
ADX_THRESHOLD = 20.0               # Minimum ADX for trending filter
ATR_PERIOD = 14
VOLUME_SURGE_MULTIPLIER = 1.5      # Flag if today vol >= 1.5x 20-day avg
MIN_AVG_TURNOVER_CR = 50.0         # ₹50 crore minimum daily turnover
WATCHLIST_SOURCE = "NIFTY500"      # Options: NIFTY200, NIFTY500

# ── Market Hours (IST) ────────────────────────────────
MARKET_OPEN = "09:15"
MARKET_CLOSE = "15:30"
SCAN_START = "09:45"                # Start scanning after OR completes

# ── Telegram ──────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_ALERTS_ENABLED = os.getenv("TELEGRAM_ALERTS_ENABLED", "FALSE").upper() == "TRUE"

# ── Paths ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOG_DIR = os.path.join(BASE_DIR, "logs")
DB_PATH = os.path.join(DATA_DIR, "picks.db")
WATCHLIST_CACHE = os.path.join(DATA_DIR, "watchlist.csv")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)
