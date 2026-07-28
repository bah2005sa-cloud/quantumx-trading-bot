import os
import time
import threading
import requests
import numpy as np
import pandas as pd
import yfinance as yf
from flask import Flask

# --- سيرفر خفيف لإبقاء الخدمة مجانية على Render ---
app = Flask(__name__)

@app.route('/')
def home():
    return "QuantumX Trading Bot is Live & Active 24/7!"

# --- بيانات التلجرام الخاصة بك ---
TELEGRAM_TOKEN = "8888568882:AAGj6udKvmFkg9wldpTgPgc7nxRhRenMDQ0"
CHAT_ID = "7691199088"

SYMBOLS_MAP = {
    "XAUUSD": "GC=F",     # الذهب
    "US30": "^DJI",       # الداو جونز
    "GER30": "^GDAXI",    # الداكس الألماني
    "EURUSD": "EURUSD=X", # اليورو
    "GBPUSD": "GBPUSD=X"  # الاسترليني
}

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram Error: {e}")

def fetch_market_data(ticker_symbol):
    try:
        df = yf.download(tickers=ticker_symbol, period="5d", interval="15m", progress=False)
        if df.empty or len(df) < 50:
            return None
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
        df.columns = ['open', 'high', 'low', 'close', 'volume']
        df['vol_ma'] = df['volume'].rolling(window=20).mean()
        df['rvol'] = df['volume'] / (df['vol_ma'] + 1e-9)
        df['sma_20'] = df['close'].rolling(window=20).mean()
        df['sma_50'] = df['close'].rolling(window=50).mean()
        return df.dropna()
    except Exception as e:
        print(f"Data Fetch Error: {e}")
        return None

def analyze_and_signal():
    for name, ticker in SYMBOLS_MAP.items():
        df = fetch_market_data(ticker)
        if df is None:
            continue
        
        latest = df.iloc[-1]
        close_price = float(latest['close'])
        rvol = float(latest['rvol'])
        
        bullish_trend = latest['sma_20'] > latest['sma_50']
        bearish_trend = latest['sma_20'] < latest['sma_50']
        
        # شرط السيولة والاتجاه
        if bullish_trend and rvol >= 1.1:
            tp1 = round(close_price * 1.004, 2)
            tp2 = round(close_price * 1.008, 2)
            sl = round(close_price * 0.996, 2)
            msg = (
                f"🏆 *إشارة شراء جديدة ({name})*\n\n"
                f"🟢 **الاتجاه:** BUY\n"
                f"📍 **سعر الدخول:** {close_price}\n"
                f"📊 **مؤشر السيولة RVOL:** {rvol:.2f}\n\n"
                f"🎯 **Target 1:** {tp1}\n"
                f"🎯 **Target 2:** {tp2}\n"
                f"🛑 **Stop Loss:** {sl}\n"
            )
            send_telegram(msg)
            
        elif bearish_trend and rvol >= 1.1:
            tp1 = round(close_price * 0.996, 2)
            tp2 = round(close_price * 0.992, 2)
            sl = round(close_price * 1.004, 2)
            msg = (
                f"🏆 *إشارة بيع جديدة ({name})*\n\n"
                f"🔴 **الاتجاه:** SELL\n"
                f"📍 **سعر الدخول:** {close_price}\n"
                f"📊 **مؤشر السيولة RVOL:** {rvol:.2f}\n\n"
                f"🎯 **Target 1:** {tp1}\n"
                f"🎯 **Target 2:** {tp2}\n"
                f"🛑 **Stop Loss:** {sl}\n"
            )
            send_telegram(msg)

def run_bot():
    send_telegram("🚀 *تم تفعيل QuantumX Trading Bot بنجاح على سحابة Render المجانية!* البوت يراقب السوق الآن.")
    while True:
        try:
            analyze_and_signal()
        except Exception as e:
            print(f"Loop Error: {e}")
        time.sleep(900) # فحص كل 15 دقيقة

# تشغيل البوت في الخلفية
threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
