import os
import math
from datetime import datetime, time as dtime

import requests
import pandas as pd
import numpy as np
from flask import Flask, request, jsonify

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "change-me")
DATA_API_KEY = os.getenv("DATA_API_KEY", "")
DATA_API_BASE = os.getenv("DATA_API_BASE", "https://eulerpool.com")
SYMBOL_MAP = {
    "EURUSD": "EURUSD",
    "GBPUSD": "GBPUSD",
    "XAUUSD": "XAUUSD",
    "GER30": "GER30",
    "US30": "US30",
}

state = {
    "last_signal": {},
}

def telegram_send(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    r = requests.post(url, json=payload, timeout=20)
    return r.ok

def fetch_ohlc(symbol, interval="15m", limit=250):
    api_symbol = SYMBOL_MAP.get(symbol, symbol)
    url = f"{DATA_API_BASE}/api/market-data"
    params = {
        "symbol": api_symbol,
        "interval": interval,
        "limit": limit,
        "apikey": DATA_API_KEY
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()

    if isinstance(data, dict) and "data" in data:
        data = data["data"]

    df = pd.DataFrame(data)
    if df.empty:
        return None

    cols = {c.lower(): c for c in df.columns}
    for need in ["open", "high", "low", "close"]:
        if need not in cols:
            raise ValueError(f"Missing column: {need}")

    df = df.rename(columns={cols["open"]: "open", cols["high"]: "high", cols["low"]: "low", cols["close"]: "close"})
    if "time" in cols:
        df = df.rename(columns={cols["time"]: "time"})
    elif "timestamp" in cols:
        df = df.rename(columns={cols["timestamp"]: "time"})
    else:
        df["time"] = pd.date_range(end=datetime.utcnow(), periods=len(df), freq="15min")

    df["time"] = pd.to_datetime(df["time"], errors="coerce")
    for c in ["open", "high", "low", "close"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)
    return df

def ema(s, span):
    return s.ewm(span=span, adjust=False).mean()

def rsi(close, period=14):
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def atr(df, period=14):
    hl = df["high"] - df["low"]
    hc = (df["high"] - df["close"].shift(1)).abs()
    lc = (df["low"] - df["close"].shift(1)).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def adx(df, period=14):
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)

    tr = pd.concat([
        (df["high"] - df["low"]),
        (df["high"] - df["close"].shift(1)).abs(),
        (df["low"] - df["close"].shift(1)).abs()
    ], axis=1).max(axis=1)

    atr_ = tr.rolling(period).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).rolling(period).mean() / atr_
    minus_di = 100 * pd.Series(minus_dm, index=df.index).rolling(period).mean() / atr_
    dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)) * 100
    return dx.rolling(period).mean()

def session_ok(symbol):
    h = datetime.utcnow().hour + 3
    if symbol in ["EURUSD", "GBPUSD"]:
        return 7 <= h <= 22
    if symbol == "XAUUSD":
        return 8 <= h <= 23
    if symbol == "GER30":
        return 9 <= h <= 18
    if symbol == "US30":
        return 14 <= h <= 23
    return True

def pair_strategy(symbol, df):
    df = df.copy()
    df["ema20"] = ema(df["close"], 20)
    df["ema50"] = ema(df["close"], 50)
    df["ema200"] = ema(df["close"], 200)
    df["rsi"] = rsi(df["close"])
    df["atr"] = atr(df)
    df["adx"] = adx(df)

    last = df.iloc[-1]
    prev = df.iloc[-2]

    if pd.isna(last["atr"]) or last["atr"] <= 0:
        return None

    price = float(last["close"])
    bias_up = last["ema50"] > last["ema200"] and price > last["ema50"]
    bias_dn = last["ema50"] < last["ema200"] and price < last["ema50"]
    strength = float(last["adx"]) if not pd.isna(last["adx"]) else 0.0
    momentum = float(last["rsi"]) if not pd.isna(last["rsi"]) else
