"""
NSE/BSE Stock Signal Dashboard
Run with:  streamlit run app.py

Fetches daily OHLC data (via yfinance), analyzes yesterday's completed candle
using moving averages, RSI, MACD, pivot points and candlestick patterns, and
shows a BUY / SELL / HOLD signal with entry, stop-loss and target.

DISCLAIMER: This tool performs technical analysis only. It does not guarantee
profit and is not financial advice. Markets involve risk of loss - always do
your own research and consider consulting a SEBI-registered advisor.
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

from analysis import generate_signal, add_all_indicators

st.set_page_config(page_title="Stock Signal Bot", layout="centered")

st.title("📈 Stock Signal Bot")
st.caption(
    "Pick a stock, get a Buy / Sell / Hold signal based on yesterday's chart. "
    "Not financial advice — for educational use only."
)

# ---------------------------------------------------------------------------
# Fixed settings (kept simple - no sliders/config for the user to worry about)
# ---------------------------------------------------------------------------
PERIOD = "6mo"
RISK_REWARD = 2.0
STOP_BUFFER_PCT = 0.5

# A curated list of well-known, liquid NSE stocks. Add more here anytime -
# format is "Display Name": "TICKER"
POPULAR_STOCKS = {
    "Reliance Industries": "RELIANCE",
    "Tata Consultancy Services (TCS)": "TCS",
    "Infosys": "INFY",
    "HDFC Bank": "HDFCBANK",
    "ICICI Bank": "ICICIBANK",
    "State Bank of India (SBI)": "SBIN",
    "Tata Motors": "TATAMOTORS",
    "Tata Steel": "TATASTEEL",
    "ITC": "ITC",
    "Larsen & Toubro (L&T)": "LT",
    "Bharti Airtel": "BHARTIARTL",
    "Maruti Suzuki": "MARUTI",
    "Wipro": "WIPRO",
    "Axis Bank": "AXISBANK",
    "Adani Enterprises": "ADANIENT",
    "Sun Pharma": "SUNPHARMA",
    "Bajaj Finance": "BAJFINANCE",
    "Hindustan Unilever (HUL)": "HINDUNILVR",
    "Kotak Mahindra Bank": "KOTAKBANK",
    "Asian Paints": "ASIANPAINT",
}

choice = st.selectbox("Choose a stock", options=list(POPULAR_STOCKS.keys()))
run_btn = st.button("Get Signal", type="primary", use_container_width=True)


def load_data(symbol, period):
    ticker = symbol.strip().upper()
    if not ticker.endswith(".NS") and not ticker.endswith(".BO"):
        ticker += ".NS"  # default to NSE
    data = yf.download(ticker, period=period, interval="1d", progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return ticker, data


def render_chart(df, symbol):
    fig = go.Figure(data=[go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"], name=symbol
    )])
    fig.add_trace(go.Scatter(x=df.index, y=df["SMA20"], line=dict(width=1), name="SMA20"))
    fig.add_trace(go.Scatter(x=df.index, y=df["SMA50"], line=dict(width=1), name="SMA50"))
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=30, b=10),
                       xaxis_rangeslider_visible=False)
    return fig


def action_badge(action):
    color = {"BUY": "🟢", "SELL": "🔴", "HOLD": "🟡"}.get(action, "⚪")
    return f"{color} **{action}**"


if run_btn:
    symbol = POPULAR_STOCKS[choice]
    with st.spinner(f"Analyzing {choice}..."):
        try:
            ticker, df = load_data(symbol, PERIOD)
            if df.empty or len(df) < 50:
                st.error("Not enough data returned for this stock. Please try again.")
            else:
                result = generate_signal(df, risk_reward=RISK_REWARD, stop_buffer_pct=STOP_BUFFER_PCT)
                df_ind = add_all_indicators(df)

                st.divider()
                st.subheader(choice)
                st.plotly_chart(render_chart(df_ind, ticker), use_container_width=True)

                st.markdown(f"#### Signal as of {result['as_of_date']}")
                st.markdown(f"## {action_badge(result['action'])}")

                c1, c2, c3 = st.columns(3)
                c1.metric("Entry", f"₹{result['entry']}")
                if result["stop_loss"] is not None:
                    c2.metric("Stop-loss", f"₹{result['stop_loss']}")
                    c3.metric("Target", f"₹{result['target']}")
                else:
                    c2.metric("Stop-loss", "—")
                    c3.metric("Target", "—")

                if result["action"] == "HOLD":
                    st.write("No trade suggested right now — the signal isn't strong enough either way.")

                st.markdown("#### Should you buy now?")
                if result["can_buy_now"]:
                    st.success(f"✅ Yes — {result['timing_advice']}")
                else:
                    st.warning(f"⏳ Not yet — {result['timing_advice']}")

                st.markdown("**Why this signal:**")
                for r in result["reasons"]:
                    st.write(f"- {r}")

        except Exception as e:
            st.error(f"Couldn't fetch data for {choice}. Please try again in a moment. ({e})")

    st.divider()
    st.caption(
        "⚠️ This is a rule-based technical analysis tool, not investment advice. "
        "Past patterns don't guarantee future price movement. Trade at your own risk."
    )
else:
    st.info("Choose a stock above and click **Get Signal**.")
