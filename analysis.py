"""
Core technical analysis engine for the stock signal bot.
Takes an OHLCV dataframe (columns: Open, High, Low, Close, Volume, indexed by date)
and produces indicators, candlestick pattern flags, and a final BUY/SELL/HOLD signal
with entry, stop-loss and target levels.

This module has no dependency on any data source - you can feed it data from
yfinance, NSE's API, a broker API, or a CSV file.
"""

import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# INDICATORS
# ---------------------------------------------------------------------------

def add_moving_averages(df, short=20, long=50):
    df = df.copy()
    df[f"SMA{short}"] = df["Close"].rolling(short).mean()
    df[f"SMA{long}"] = df["Close"].rolling(long).mean()
    df["EMA9"] = df["Close"].ewm(span=9, adjust=False).mean()
    return df


def add_rsi(df, period=14):
    df = df.copy()
    delta = df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI"] = 100 - (100 / (1 + rs))
    df["RSI"] = df["RSI"].fillna(50)
    return df


def add_macd(df, fast=12, slow=26, signal=9):
    df = df.copy()
    ema_fast = df["Close"].ewm(span=fast, adjust=False).mean()
    ema_slow = df["Close"].ewm(span=slow, adjust=False).mean()
    df["MACD"] = ema_fast - ema_slow
    df["MACD_signal"] = df["MACD"].ewm(span=signal, adjust=False).mean()
    df["MACD_hist"] = df["MACD"] - df["MACD_signal"]
    return df


def add_pivot_points(df):
    """Classic pivot points computed from the PREVIOUS day's H/L/C.
    These become today's support/resistance reference levels."""
    df = df.copy()
    prev_high = df["High"].shift(1)
    prev_low = df["Low"].shift(1)
    prev_close = df["Close"].shift(1)

    pivot = (prev_high + prev_low + prev_close) / 3
    df["Pivot"] = pivot
    df["R1"] = 2 * pivot - prev_low
    df["S1"] = 2 * pivot - prev_high
    df["R2"] = pivot + (prev_high - prev_low)
    df["S2"] = pivot - (prev_high - prev_low)
    return df


def add_all_indicators(df):
    df = add_moving_averages(df)
    df = add_rsi(df)
    df = add_macd(df)
    df = add_pivot_points(df)
    return df


# ---------------------------------------------------------------------------
# CANDLESTICK PATTERNS (evaluated on the most recent completed candle,
# i.e. "yesterday's candle")
# ---------------------------------------------------------------------------

def _body(row):
    return abs(row["Close"] - row["Open"])


def _range(row):
    return row["High"] - row["Low"]


def detect_patterns(df):
    """Returns a dict of pattern_name -> bool for the LAST row of df,
    using up to 3 preceding candles where needed."""
    patterns = {}
    if len(df) < 3:
        return patterns

    c0 = df.iloc[-1]   # yesterday (most recent completed candle)
    c1 = df.iloc[-2]   # day before
    c2 = df.iloc[-3]

    body0, range0 = _body(c0), _range(c0)
    body1, range1 = _body(c1), _range(c1)

    is_bull0 = c0["Close"] > c0["Open"]
    is_bull1 = c1["Close"] > c1["Open"]

    # Doji: very small body relative to range
    patterns["doji"] = range0 > 0 and body0 <= 0.1 * range0

    # Hammer: small body near top of range, long lower wick, in a downtrend context
    lower_wick0 = min(c0["Open"], c0["Close"]) - c0["Low"]
    upper_wick0 = c0["High"] - max(c0["Open"], c0["Close"])
    patterns["hammer"] = (
        range0 > 0
        and lower_wick0 >= 2 * body0
        and upper_wick0 <= 0.3 * body0
        and body0 > 0
    )

    # Shooting star: small body near bottom of range, long upper wick
    patterns["shooting_star"] = (
        range0 > 0
        and upper_wick0 >= 2 * body0
        and lower_wick0 <= 0.3 * body0
        and body0 > 0
    )

    # Bullish engulfing: red candle followed by a green candle that engulfs its body
    patterns["bullish_engulfing"] = (
        not is_bull1 and is_bull0
        and c0["Close"] > c1["Open"]
        and c0["Open"] < c1["Close"]
    )

    # Bearish engulfing: green candle followed by a red candle that engulfs its body
    patterns["bearish_engulfing"] = (
        is_bull1 and not is_bull0
        and c0["Open"] > c1["Close"]
        and c0["Close"] < c1["Open"]
    )

    # Morning star (3-candle bullish reversal): big red, small body gap down, big green
    body2 = _body(c2)
    is_bull2 = c2["Close"] > c2["Open"]
    patterns["morning_star"] = (
        not is_bull2 and body2 > 0
        and body1 < body2 * 0.5
        and is_bull0
        and c0["Close"] > (c2["Open"] + c2["Close"]) / 2
    )

    # Evening star (3-candle bearish reversal)
    patterns["evening_star"] = (
        is_bull2 and body2 > 0
        and body1 < body2 * 0.5
        and not is_bull0
        and c0["Close"] < (c2["Open"] + c2["Close"]) / 2
    )

    return patterns


# ---------------------------------------------------------------------------
# SIGNAL ENGINE - combines indicators + patterns into BUY/SELL/HOLD
# ---------------------------------------------------------------------------

BULLISH_PATTERNS = {"hammer", "bullish_engulfing", "morning_star"}
BEARISH_PATTERNS = {"shooting_star", "bearish_engulfing", "evening_star"}


def generate_signal(df, risk_reward=2.0, stop_buffer_pct=0.5):
    """
    df: OHLCV dataframe with at least 50 rows, most recent row = yesterday's
        completed candle (i.e. the last full trading day).
    Returns a dict describing the recommended action.
    """
    df = add_all_indicators(df)
    patterns = detect_patterns(df)
    last = df.iloc[-1]

    score = 0
    reasons = []

    # --- Trend (moving averages) ---
    if pd.notna(last["SMA20"]) and pd.notna(last["SMA50"]):
        if last["Close"] > last["SMA20"] > last["SMA50"]:
            score += 2
            reasons.append("Price above SMA20 & SMA50 (uptrend)")
        elif last["Close"] < last["SMA20"] < last["SMA50"]:
            score -= 2
            reasons.append("Price below SMA20 & SMA50 (downtrend)")

    # --- RSI ---
    if last["RSI"] < 30:
        score += 1.5
        reasons.append(f"RSI oversold ({last['RSI']:.1f})")
    elif last["RSI"] > 70:
        score -= 1.5
        reasons.append(f"RSI overbought ({last['RSI']:.1f})")

    # --- MACD ---
    if last["MACD"] > last["MACD_signal"]:
        score += 1
        reasons.append("MACD above signal line (bullish momentum)")
    else:
        score -= 1
        reasons.append("MACD below signal line (bearish momentum)")

    # --- Candlestick patterns ---
    for p in BULLISH_PATTERNS:
        if patterns.get(p):
            score += 2
            reasons.append(f"Bullish candlestick pattern: {p.replace('_',' ')}")
    for p in BEARISH_PATTERNS:
        if patterns.get(p):
            score -= 2
            reasons.append(f"Bearish candlestick pattern: {p.replace('_',' ')}")
    if patterns.get("doji"):
        reasons.append("Doji detected (indecision - lower confidence)")
        score *= 0.7

    # --- Decide action ---
    if score >= 2.5:
        action = "BUY"
    elif score <= -2.5:
        action = "SELL"
    else:
        action = "HOLD"

    entry = float(last["Close"])
    day_low = float(last["Low"])
    day_high = float(last["High"])
    r1 = float(last["R1"]) if pd.notna(last["R1"]) else None
    s1 = float(last["S1"]) if pd.notna(last["S1"]) else None

    if action == "BUY":
        stop_loss = min(day_low, last["S1"] if pd.notna(last["S1"]) else day_low)
        stop_loss = stop_loss * (1 - stop_buffer_pct / 100)
        risk = entry - stop_loss
        target = entry + risk * risk_reward
    elif action == "SELL":
        stop_loss = max(day_high, last["R1"] if pd.notna(last["R1"]) else day_high)
        stop_loss = stop_loss * (1 + stop_buffer_pct / 100)
        risk = stop_loss - entry
        target = entry - risk * risk_reward
    else:
        stop_loss = None
        target = None

    # --- Buy-now vs wait-and-watch guidance ---
    if action == "BUY":
        can_buy_now = True
        timing_advice = (
            "Conditions look favorable right now — you could consider buying "
            "near the current price, using the stop-loss and target above to manage risk."
        )
    elif action == "SELL":
        can_buy_now = False
        timing_advice = (
            "This isn't a good time to buy — the stock is showing bearish signals. "
            "If you already own it, your stop-loss above is there to protect you. "
            "Wait for a clear reversal — price reclaiming its moving averages, RSI "
            "recovering from oversold, or a bullish reversal candle — before considering a fresh buy."
        )
    else:  # HOLD
        can_buy_now = False
        if score > 0:
            if last["RSI"] > 65:
                timing_advice = (
                    f"The trend is leaning positive, but RSI is a bit high ({last['RSI']:.1f}). "
                    + (f"Wait for the price to cool off toward the support level (₹{s1:.2f}) "
                       if s1 else "Wait for RSI to ease back toward 50-60 ")
                    + "or for a clear bullish candlestick pattern before buying."
                )
            else:
                timing_advice = (
                    "The trend is leaning positive but not confirmed yet. "
                    + (f"Wait for the price to close above the resistance level (₹{r1:.2f}) "
                       if r1 else "Wait for a confirmed breakout ")
                    + "or for a bullish candlestick pattern before buying."
                )
        elif score < 0:
            timing_advice = (
                "The trend is leaning negative right now — it's better to wait. "
                "Watch for price reclaiming its 20/50-day moving averages, RSI recovering "
                "from oversold, or a bullish reversal candle before considering a buy."
            )
        else:
            timing_advice = (
                "Signals are mixed — no clear edge either way yet. "
                + (f"Wait for either a breakout above ₹{r1:.2f} (resistance) or a pullback to "
                   f"₹{s1:.2f} (support) " if r1 and s1 else "Wait for a clearer trend ")
                + "before buying."
            )

    return {
        "action": action,
        "score": round(score, 2),
        "entry": round(entry, 2),
        "stop_loss": round(stop_loss, 2) if stop_loss is not None else None,
        "target": round(target, 2) if target is not None else None,
        "can_buy_now": can_buy_now,
        "timing_advice": timing_advice,
        "rsi": round(float(last["RSI"]), 2),
        "macd": round(float(last["MACD"]), 3),
        "sma20": round(float(last["SMA20"]), 2) if pd.notna(last["SMA20"]) else None,
        "sma50": round(float(last["SMA50"]), 2) if pd.notna(last["SMA50"]) else None,
        "pivot": round(float(last["Pivot"]), 2) if pd.notna(last["Pivot"]) else None,
        "patterns_detected": [k for k, v in patterns.items() if v],
        "reasons": reasons,
        "as_of_date": str(df.index[-1]).split(" ")[0],
    }
