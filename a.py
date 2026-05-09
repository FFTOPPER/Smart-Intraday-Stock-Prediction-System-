# ===============================
# IMPORTS
# ===============================
import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
import ta

# ===============================
# FETCH LIVE DATA
# ===============================
df = yf.download(
    "RELIANCE.NS",
    period="5d",
    interval="5m",
    auto_adjust=False,
    progress=False
)

# ===============================
# FIX COLUMN ISSUE (IMPORTANT)
# ===============================
df.columns = df.columns.get_level_values(0)

# ===============================
# TECHNICAL INDICATORS
# ===============================

# RSI
df['RSI'] = ta.momentum.RSIIndicator(df['Close']).rsi()

# MACD
macd = ta.trend.MACD(df['Close'])
df['MACD'] = macd.macd()
df['MACD_Signal'] = macd.macd_signal()

# EMA
df['EMA_20'] = ta.trend.EMAIndicator(df['Close'], window=20).ema_indicator()

# Bollinger Bands
bb = ta.volatility.BollingerBands(df['Close'])
df['BB_Upper'] = bb.bollinger_hband()
df['BB_Lower'] = bb.bollinger_lband()

# ADX
df['ADX'] = ta.trend.ADXIndicator(
    df['High'], df['Low'], df['Close']
).adx()

# ATR
df['ATR'] = ta.volatility.AverageTrueRange(
    df['High'], df['Low'], df['Close']
).average_true_range()

# Volume Oscillator
df['Volume_MA_Short'] = df['Volume'].rolling(5).mean()
df['Volume_MA_Long'] = df['Volume'].rolling(20).mean()
df['Volume_Oscillator'] = df['Volume_MA_Short'] - df['Volume_MA_Long']

# ===============================
# DROP NaNs
# ===============================
df.dropna(inplace=True)

# ===============================
# SIMPLE LINE CHARTS
# ===============================

plt.figure(figsize=(14, 28))

# 1️⃣ Price
plt.subplot(8, 1, 1)
plt.plot(df.index, df['Close'], label='Close Price', color='black')
plt.title("Price Movement")
plt.legend()

# 2️⃣ RSI
plt.subplot(8, 1, 2)
plt.plot(df.index, df['RSI'], label='RSI', color='purple')
plt.axhline(70, linestyle='--', color='red')
plt.axhline(30, linestyle='--', color='green')
plt.title("RSI Indicator")
plt.legend()

# 3️⃣ MACD
plt.subplot(8, 1, 3)
plt.plot(df.index, df['MACD'], label='MACD', color='blue')
plt.plot(df.index, df['MACD_Signal'], label='Signal', color='orange')
plt.title("MACD Indicator")
plt.legend()

# 4️⃣ EMA
plt.subplot(8, 1, 4)
plt.plot(df.index, df['Close'], label='Price', color='black')
plt.plot(df.index, df['EMA_20'], label='EMA 20', color='green')
plt.title("EMA Indicator")
plt.legend()

# 5️⃣ Bollinger Bands
plt.subplot(8, 1, 5)
plt.plot(df.index, df['Close'], label='Price', color='black')
plt.plot(df.index, df['BB_Upper'], label='Upper Band', linestyle='--', color='red')
plt.plot(df.index, df['BB_Lower'], label='Lower Band', linestyle='--', color='green')
plt.title("Bollinger Bands")
plt.legend()

# 6️⃣ ADX
plt.subplot(8, 1, 6)
plt.plot(df.index, df['ADX'], label='ADX', color='brown')
plt.axhline(25, linestyle='--', color='gray')
plt.title("ADX Indicator")
plt.legend()

# 7️⃣ ATR
plt.subplot(8, 1, 7)
plt.plot(df.index, df['ATR'], label='ATR', color='darkcyan')
plt.title("ATR Indicator")
plt.legend()

# 8️⃣ Volume Oscillator
plt.subplot(8, 1, 8)
plt.plot(df.index, df['Volume_Oscillator'], label='Volume Oscillator', color='magenta')
plt.title("Volume Oscillator")
plt.legend()

plt.tight_layout()
plt.show()
