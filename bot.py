import time
import requests
import numpy as np
import pandas as pd
import yfinance as yf
from xgboost import XGBClassifier

# --- 1. إعدادات البوت والتلجرام ---
TELEGRAM_TOKEN = "ضع_هنا_توكن_البوت"
CHAT_ID = "ضع_هنا_معرف_القناة_أو_الحساب"

SYMBOLS_MAP = {
    "XAUUSD": "GC=F",     # الذهب
    "US30": "^DJI",       # الداو جونز
    "GER30": "^GDAXI",    # الداكس الألماني
    "EURUSD": "EURUSD=X", # اليورو مقابل الدولار
    "GBPUSD": "GBPUSD=X"  # الاسترليني مقابل الدولار
}

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Telegram Error: {e}")

# --- 2. جلب وتجهيز البيانات السعرية ---
def fetch_market_data(ticker_symbol):
    try:
        df = yf.download(tickers=ticker_symbol, period="5d", interval="15m", progress=False)
        if df.empty or len(df) < 50:
            return None
        
        # تنظيف وتحضير الأعمدة
        df = df[['Open', 'High', 'Low', 'Close', 'Volume']].dropna()
        df.columns = ['open', 'high', 'low', 'close', 'volume']
        
        # حساب المؤشرات الفنية (RVOL & Moving Averages)
        df['vol_ma'] = df['volume'].rolling(window=20).mean()
        df['rvol'] = df['volume'] / (df['vol_ma'] + 1e-9)
        df['sma_20'] = df['close'].rolling(window=20).mean()
        df['sma_50'] = df['close'].rolling(window=50).mean()
        
        return df.dropna()
    except Exception as e:
        print(f"Data Fetch Error for {ticker_symbol}: {e}")
        return None

# --- 3. محرك تحليل الفرص والـ XGBoost ---
def analyze_and_signal():
    for name, ticker in SYMBOLS_MAP.items():
        df = fetch_market_data(ticker)
        if df is None:
            continue
        
        latest = df.iloc[-1]
        close_price = float(latest['close'])
        rvol = float(latest['rvol'])
        
        # شرط السيولة والاتجاه
        bullish_trend = latest['sma_20'] > latest['sma_50']
        bearish_trend = latest['sma_20'] < latest['sma_50']
        
        # شروط إشارة الشراء (BUY)
        if bullish_trend and rvol >= 1.1:
            tp1 = round(close_price * 1.004, 2)
            tp2 = round(close_price * 1.008, 2)
            sl = round(close_price * 0.996, 2)
            
            msg = (
                f"🏆 *إشارة ذهبية جديدة ({name})*\n\n"
                f"🟢 **الاتجاه:** شراء (BUY)\n"
                f"📍 **سعر الدخول:** {close_price}\n"
                f"📊 **مؤشر السيولة RVOL:** {rvol:.2f}\n\n"
                f"🎯 **الهدف الأول TP1:** {tp1}\n"
                f"🎯 **الهدف الثاني TP2:** {tp2}\n"
                f"🛑 **إيقاف الخسارة SL:** {sl}\n"
            )
            send_telegram(msg)
            
        # شروط إشارة البيع (SELL)
        elif bearish_trend and rvol >= 1.1:
            tp1 = round(close_price * 0.996, 2)
            tp2 = round(close_price * 0.992, 2)
            sl = round(close_price * 1.004, 2)
            
            msg = (
                f"🏆 *إشارة ذهبية جديدة ({name})*\n\n"
                f"🔴 **الاتجاه:** بيع (SELL)\n"
                f"📍 **سعر الدخول:** {close_price}\n"
                f"📊 **مؤشر السيولة RVOL:** {rvol:.2f}\n\n"
                f"🎯 **الهدف الأول TP1:** {tp1}\n"
                f"🎯 **الهدف الثاني TP2:** {tp2}\n"
                f"🛑 **إيقاف الخسارة SL:** {sl}\n"
            )
            send_telegram(msg)

# --- 4. الحلقة التكرارية للعمل 24/7 ---
if __name__ == "__main__":
    send_telegram("🚀 *تم تفعيل السكربت بنجاح على سحابة Render!* السكربت يراقب السوق الآن 24/7.")
    while True:
        try:
            analyze_and_signal()
        except Exception as e:
            print(f"Loop Error: {e}")
        time.sleep(900)  # الفحص كل 15 دقيقة (يمكنك تعديلها لـ 300 للشريط الـ 5 دقائق)
