# ===============================
# Imports
# ===============================
import matplotlib
matplotlib.use("Agg")

from flask import Flask, render_template, send_from_directory, jsonify, request
import yfinance as yf
import pandas as pd
import numpy as np
import joblib
import os
import ta
import mplfinance as mpf
from datetime import datetime, time as dtime
import pytz

# ===============================
# Configuration
# ===============================
CHART_DIR = "charts"
os.makedirs(CHART_DIR, exist_ok=True)

# ===============================
# COMPANY CONFIG (🔥 MAIN ADDITION)
# ===============================
COMPANIES = {
    "RELIANCE": {"symbol": "RELIANCE.NS", "model": "trend_model.pkl"},
    "TCS": {"symbol": "TCS.NS", "model": "TCS.pkl"},
    "INFY": {"symbol": "INFY.NS", "model": "INFY.pkl"},
    "HDFCBANK": {"symbol": "HDFCBANK.NS", "model": "HDFCBANK.pkl"},
    "ICICIBANK": {"symbol": "ICICIBANK.NS", "model": "ICICIBANK.pkl"},
    "WIPRO": {"symbol": "WIPRO.NS", "model": "WIPRO.pkl"},
    "ITC": {"symbol": "ITC.NS", "model": "ITC.pkl"},
    "AXISBANK": {"symbol": "AXISBANK.NS", "model": "AXISBANK.pkl"},
    "LT": {"symbol": "LT.NS", "model": "LT.pkl"},
    "HINDUNILVR": {"symbol": "HINDUNILVR.NS", "model": "HINDUNILVR.pkl"}
}

DEFAULT_COMPANY = "RELIANCE"

# ===============================
# Feature Order (MUST MATCH TRAINING)
# ===============================
features = [
    'Close',
    'hl_range',
    'oc_change',
    'pct_change',
    'ma_5',
    'ma_10',
    'ma_20',
    'rsi',
    'adx',
    'macd',
    'macd_signal',
    'macd_diff',
    'bb_width'
]

# ===============================
# Flask App
# ===============================
app = Flask(__name__)

# ===============================
# Market Status (NSE)
# ===============================
def get_market_status():
    ist = pytz.timezone("Asia/Kolkata")
    now = datetime.now(ist)

    if now.weekday() >= 5:
        return "CLOSED", now

    if dtime(9, 15) <= now.time() <= dtime(15, 30):
        return "OPEN", now

    return "CLOSED", now

# ===============================
# Next Candle Countdown
# ===============================
def get_next_candle_countdown():
    status, now = get_market_status()
    if status == "CLOSED":
        return None, None

    minute = (now.minute // 5 + 1) * 5
    if minute >= 60:
        next_candle = now.replace(hour=now.hour + 1, minute=0, second=0)
    else:
        next_candle = now.replace(minute=minute, second=0)

    return next_candle.strftime('%H:%M IST'), int((next_candle - now).total_seconds())

# ===============================
# Fetch Live Data
# ===============================
def fetch_live_data(symbol, interval="5m"):
    period_map = {
        "5m": "10d",
        "15m": "30d",
        "30m": "60d"
    }

    df = yf.download(
        tickers=symbol,
        interval=interval,
        period=period_map.get(interval, "10d"),
        auto_adjust=False,
        progress=False
    )

    if df.empty:
        return df

    df.columns = df.columns.get_level_values(0)
    df.reset_index(inplace=True)
    df['Datetime'] = pd.to_datetime(df['Datetime'], utc=True).dt.tz_convert("Asia/Kolkata")
    return df

# ===============================
# Filter Trading Days
# ===============================
def filter_trading_days(df, days):
    if df.empty:
        return df

    unique_days = sorted(df['Datetime'].dt.date.unique())

    if days == "today":
        keep_days = unique_days[-1:]
    elif days == "2d":
        keep_days = unique_days[-2:]
    elif days == "5d":
        keep_days = unique_days[-5:]
    else:
        keep_days = unique_days

    return df[df['Datetime'].dt.date.isin(keep_days)]

# ===============================
# Feature Engineering
# ===============================
def prepare_features(df):
    if df.empty:
        return df

    df = df.copy()

    df['hl_range'] = df['High'] - df['Low']
    df['oc_change'] = df['Close'] - df['Open']
    df['pct_change'] = df['Close'].pct_change() * 100

    df['ma_5'] = df['Close'].rolling(5).mean()
    df['ma_10'] = df['Close'].rolling(10).mean()
    df['ma_20'] = df['Close'].rolling(20).mean()

    df['ema_20'] = ta.trend.EMAIndicator(df['Close'], window=20).ema_indicator()

    df['rsi'] = ta.momentum.RSIIndicator(df['Close']).rsi()

    macd = ta.trend.MACD(df['Close'])
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    df['macd_diff'] = macd.macd_diff()

    df['adx'] = ta.trend.ADXIndicator(df['High'], df['Low'], df['Close']).adx()

    bb = ta.volatility.BollingerBands(df['Close'])
    df['bb_upper'] = bb.bollinger_hband()
    df['bb_lower'] = bb.bollinger_lband()
    df['bb_width'] = bb.bollinger_wband()

    df['atr'] = ta.volatility.AverageTrueRange(
        df['High'], df['Low'], df['Close']
    ).average_true_range()

    df['vol_osc'] = (
        df['Volume'].rolling(5).mean() -
        df['Volume'].rolling(10).mean()
    )

    return df.dropna()

# ===============================
# Signal Helpers
# ===============================
def final_signal(cls):
    return "BUY" if cls >= 2 else "HOLD" if cls == 1 else "SELL"

def numeric_signal(signal):
    return 1 if signal == "BUY" else 0 if signal == "HOLD" else -1

# ===============================
# PNG Chart
# ===============================
def plot_live_chart(df, signal, symbol, timestamp):
    df_plot = df.tail(30).set_index('Datetime')

    time_str = pd.to_datetime(timestamp).strftime('%Y-%m-%d_%H-%M')
    filename = f"{symbol}_{time_str}.png"
    path = f"{CHART_DIR}/{filename}"

    mpf.plot(
        df_plot,
        type='candle',
        style='yahoo',
        volume=True,
        title=f"{symbol} | Signal: {signal}",
        savefig=path,
        show_nontrading=False
    )

    return filename

def generate_simple_reason(row, cls):
    msgs = []

    msgs.append(
        "Buying pressure is stronger than selling pressure"
        if row['macd_diff'] > 0
        else "Selling pressure is stronger than buying pressure"
    )

    msgs.append(
        "Market trend is strong"
        if row['adx'] > 25
        else "Market trend is weak"
    )

    msgs.append(
        "Conditions are favorable for buying"
        if cls >= 2
        else "Waiting is safer before taking action"
        if cls == 1
        else "Not a good time to buy"
    )

    return ". ".join(msgs) + "."

def generate_technical_reason(row):
    reasons = []

    reasons.append(
        "Bullish MACD momentum"
        if row['macd_diff'] > 0
        else "Bearish MACD momentum"
    )

    if row['rsi'] > 70:
        reasons.append("RSI indicates overbought conditions")
    elif row['rsi'] < 30:
        reasons.append("RSI indicates oversold conditions")
    else:
        reasons.append("RSI is in neutral range")

    reasons.append(
        "Strong trend strength (ADX > 25)"
        if row['adx'] > 25
        else "Weak trend strength (ADX < 25)"
    )

    reasons.append(
        "Price trading above 20-period moving average"
        if row['Close'] > row['ma_20']
        else "Price trading below 20-period moving average"
    )

    return ", ".join(reasons) + "."


# ===============================
# Latest Prediction
# ===============================
def predict_live_signal(company):
    cfg = COMPANIES[company]
    symbol = cfg["symbol"]
    model = joblib.load(cfg["model"])

    df_raw = fetch_live_data(symbol, "5m")
    df = prepare_features(df_raw)
    latest = df.iloc[-1:]

    X = latest[features]
    proba = model.predict_proba(X)

    cls = int(np.argmax(proba))
    conf = float(np.max(proba)) * 100
    signal = final_signal(cls)

    chart_file = plot_live_chart(
        df_raw,
        signal,
        symbol.replace(".NS", ""),
        latest['Datetime'].values[0]
    )

    return {
    "Company": company,
    "Symbol": symbol,
    "Datetime": latest['Datetime'].values[0],
    "Price": float(latest['Close'].values[0]),
    "Signal": signal,
    "Confidence": f"{conf:.2f}%",
    "Simple Reason": generate_simple_reason(latest.iloc[0], cls),
    "Technical Reason": generate_technical_reason(latest.iloc[0]),
    "Chart_Image": chart_file
}


# ===============================
# ROUTES
# ===============================
@app.route("/")
@app.route("/")
def index():
    company = request.args.get("company", DEFAULT_COMPANY)
    interval = request.args.get("interval", "5m")
    days = request.args.get("days", "today")

    result = predict_live_signal(company)

    status, now = get_market_status()
    next_candle, countdown = get_next_candle_countdown()

    return render_template(
        "index.html",
        companies=COMPANIES.keys(),
        selected_company=company,
        selected_interval=interval,   # ✅ ADDED
        selected_days=days,           # ✅ ADDED
        result=result,
        chart_file=result["Chart_Image"],
        market_status=status,
        current_time=now.strftime('%Y-%m-%d %H:%M:%S IST'),
        next_candle_time=next_candle,
        countdown_seconds=countdown
    )

@app.route("/live-data")
def live_data():
    company = request.args.get("company", DEFAULT_COMPANY)
    interval = request.args.get("interval", "5m")
    days = request.args.get("days", "today")

    symbol = COMPANIES[company]["symbol"]
    df = fetch_live_data(symbol, interval)
    df = filter_trading_days(df, days)

    return jsonify({
        "time": df['Datetime'].astype(str).tolist(),
        "open": df['Open'].tolist(),
        "high": df['High'].tolist(),
        "low": df['Low'].tolist(),
        "close": df['Close'].tolist()
    })

@app.route("/signal-data")
def signal_data():
    company = request.args.get("company", DEFAULT_COMPANY)
    interval = request.args.get("interval", "5m")
    days = request.args.get("days", "today")

    symbol = COMPANIES[company]["symbol"]
    model = joblib.load(COMPANIES[company]["model"])

    df = prepare_features(fetch_live_data(symbol, interval))
    df = filter_trading_days(df, days)

    X = df[features]
    preds = model.predict(X)

    return jsonify({
        "time": df['Datetime'].astype(str).tolist(),
        "signal": [numeric_signal(final_signal(int(p))) for p in preds]
    })

@app.route("/indicator-data")
def indicator_data():
    company = request.args.get("company", DEFAULT_COMPANY)
    interval = request.args.get("interval", "5m")

    symbol = COMPANIES[company]["symbol"]
    df = prepare_features(fetch_live_data(symbol, interval)).tail(80)

    return jsonify({
        "time": df['Datetime'].astype(str).tolist(),
        "rsi": df['rsi'].tolist(),
        "macd": df['macd'].tolist(),
        "macd_signal": df['macd_signal'].tolist(),
        "ema": df['ema_20'].tolist(),
        "bb_upper": df['bb_upper'].tolist(),
        "bb_lower": df['bb_lower'].tolist(),
        "adx": df['adx'].tolist(),
        "atr": df['atr'].tolist(),
        "vol_osc": df['vol_osc'].tolist()
    })

@app.route("/charts/<path:filename>")
def charts(filename):
    return send_from_directory(CHART_DIR, filename)

# ===============================
# Run App
# ===============================
if __name__ == "__main__":
    app.run(debug=True)
