# NSE/BSE Stock Signal Bot

A web dashboard that analyzes the **previous trading day's candle** for stocks
you choose (NSE/BSE) and gives a **BUY / SELL / HOLD** signal with an entry
price, stop-loss, and target — based purely on technical analysis (moving
averages, RSI, MACD, pivot support/resistance, and candlestick patterns like
hammer, engulfing, morning/evening star, doji).

## ⚠️ Important disclaimer
This is a **rule-based technical analysis tool**, not a prediction engine and
not financial advice. It cannot foresee news, earnings surprises, or market
shocks. Use it as one input among many, size positions carefully, and always
respect your own stop-loss. Consider consulting a SEBI-registered advisor for
real investment decisions.

## Files
- `analysis.py` — the core engine: indicators, candlestick pattern detection,
  and the signal-scoring logic. Data-source agnostic (feed it any OHLCV
  dataframe).
- `app.py` — the Streamlit web dashboard. Fetches data via `yfinance` and
  calls `analysis.py`.
- `requirements.txt` — Python dependencies.

## How to run it

1. Install Python 3.9+ if you don't have it.
2. In this folder, install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Launch the dashboard:
   ```bash
   streamlit run app.py
   ```
4. It opens in your browser (usually `http://localhost:8501`). Pick a stock
   from the dropdown and click **Get Signal**.

## How the signal is built

1. **Trend** — is price above/below its 20-day and 50-day moving averages?
2. **Momentum** — RSI(14) for overbought (>70) / oversold (<30); MACD line vs.
   its signal line.
3. **Candlestick pattern** on yesterday's candle — bullish (hammer, bullish
   engulfing, morning star) or bearish (shooting star, bearish engulfing,
   evening star), with doji flagged as low-confidence/indecision.
4. **Support/resistance** — classic pivot points computed from the prior
   day's high/low/close, used to set the stop-loss.
5. All of the above are combined into a score. Above a threshold → **BUY**,
   below → **SELL**, otherwise → **HOLD** (no trade suggested).
6. **Stop-loss** is placed just beyond the nearest support/resistance level
   (plus a small buffer you control). **Target** is set using your chosen
   risk:reward ratio (default 1:2).

## Adding more stocks to the dropdown
Open `app.py` and add a line to the `POPULAR_STOCKS` dictionary, e.g.:
```python
"Zomato": "ZOMATO",
```
The left side is what shows in the dropdown, the right side is the NSE ticker
symbol (without `.NS` - the app adds that automatically).

## Publishing it so anyone can use it (free)

The easiest way is **Streamlit Community Cloud** — it's made specifically for
apps like this, and it's free.

1. **Create a GitHub account** (if you don't have one): [github.com/signup](https://github.com/signup)
2. **Create a new repository**:
   - Click the `+` icon (top right) → "New repository"
   - Give it a name, e.g. `stock-signal-bot`
   - Set it to **Public**
   - Click "Create repository"
3. **Upload your files**:
   - On the new repo page, click "uploading an existing file"
   - Drag in `app.py`, `analysis.py`, `requirements.txt`, and `README.md`
   - Click "Commit changes"
4. **Deploy on Streamlit**:
   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Sign in with your GitHub account
   - Click "New app"
   - Choose your repo, branch (`main`), and set the main file path to `app.py`
   - Click "Deploy"
5. Wait 1-2 minutes — you'll get a public URL like
   `https://your-app-name.streamlit.app` that anyone can open in a browser,
   on any device, with no installation needed.

**Things to know about the free tier:**
- The app "sleeps" after a period of no visitors and takes ~30 seconds to
  wake up on the next visit — this is normal and free.
- The app and its code are public by default (since the GitHub repo is
  public). If you don't want the code visible, you can make the GitHub repo
  private — Streamlit Community Cloud still works with private repos once
  you connect your GitHub account, it just won't be visible to others browsing GitHub.
- If your app gets heavy traffic or you want more control (custom domain,
  guaranteed uptime), look at paid options later like Streamlit Cloud's paid
  tier, Render, or Railway — but for sharing with friends/personal use, the
  free tier is enough.

## Ways to extend this further
- Add more patterns (three white soldiers, harami, etc.) in `analysis.py`.
- Add volume-based confirmation (e.g. only trust a breakout if volume is
  above its 20-day average).
- Swap `yfinance` for a broker API (Zerodha Kite Connect, Upstox API, Angel
  One SmartAPI) if you want live intraday data instead of daily candles —
  those need paid/authenticated API access but give faster data.
- Add email/Telegram alerts when a new BUY/SELL signal appears for stocks in
  your watchlist.
- Backtest the signal logic against historical data before trusting it with
  real money — `analysis.py`'s `generate_signal()` can be run in a loop over
  historical windows to see how it would have performed.
