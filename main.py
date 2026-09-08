import os
import matplotlib.pyplot as plt
import mplfinance as mpf
import pandas as pd
import requests
import yfinance as yf

# Environment Variables dari Cloud / Local
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Porsi modal per saham (Rp 1.500.000)
CAPITAL_PER_POSITION = 1500000

# Watchlist Saham Likuid IHSG
WATCHLIST = [
    "BBCA.JK",
    "BBRI.JK",
    "BMRI.JK",
    "BBNI.JK",
    "TLKM.JK",
    "ASII.JK",
    "AMRT.JK",
    "ICBP.JK",
    "INDF.JK",
    "UNVR.JK",
    "CPIN.JK",
    "KLBF.JK",
    "PGAS.JK",
    "PTBA.JK",
    "ADRO.JK",
    "MDKA.JK",
    "ANTM.JK",
    "INKP.JK",
    "MEDC.JK",
    "AKRA.JK",
]


def send_telegram_text(message):
    """Kirim pesan teks biasa ke Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(message)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Gagal mengirim teks ke Telegram: {e}")


def send_telegram_photo(image_path, caption):
    """Kirim file gambar chart beserta caption ke Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print(caption)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    try:
        with open(image_path, "rb") as photo:
            payload = {
                "chat_id": TELEGRAM_CHAT_ID,
                "caption": caption,
                "parse_mode": "Markdown",
            }
            files = {"photo": photo}
            requests.post(url, data=payload, files=files, timeout=20)
    except Exception as e:
        print(f"Gagal mengirim foto ke Telegram: {e}")


def calculate_atr(df, period=14):
    """Menghitung Average True Range (ATR)."""
    high = df["High"]
    low = df["Low"]
    close = df["Close"]

    tr1 = high - low
    tr2 = (high - close.shift(1)).abs()
    tr3 = (low - close.shift(1)).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def calculate_rsi(series, period=14):
    """Menghitung Relative Strength Index (RSI) dengan Wilder's Smoothing."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -1 * delta.clip(upper=0)

    ema_gain = gain.ewm(com=period - 1, adjust=False).mean()
    ema_loss = loss.ewm(com=period - 1, adjust=False).mean()

    rs = ema_gain / ema_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def check_ihsg_trend():
    """Memeriksa apakah IHSG berada di atas MA50 (Filter Pasar Bullish)."""
    try:
        df = yf.download("^JKSE", period="100d", interval="1d", progress=False)
        if df.empty:
            return True

        close = (
            df["Close"]["^JKSE"]
            if isinstance(df.columns, pd.MultiIndex)
            else df["Close"]
        )
        ma50 = close.rolling(window=50).mean()

        return float(close.iloc[-1]) > float(ma50.iloc[-1])
    except Exception as e:
        print(f"Error checking IHSG: {e}")
        return True


def generate_chart(df, ticker):
    """Membuat gambar chart candlestick 50 hari terakhir beserta garis EMA20 & EMA50."""
    ticker_clean = ticker.replace(".JK", "")
    df_chart = df.tail(50).copy()

    close = df_chart["Close"]
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema50 = close.ewm(span=50, adjust=False).mean()

    add_plots = [
        mpf.make_addplot(ema20, color="blue", width=1.2),
        mpf.make_addplot(ema50, color="orange", width=1.2),
    ]

    filename = f"{ticker_clean}_chart.png"
    mpf.plot(
        df_chart,
        type="candle",
        style="yahoo",
        volume=True,
        addplot=add_plots,
        title=f"{ticker_clean} - Daily (Blue: EMA20, Orange: EMA50)",
        savefig=filename,
    )
    return filename


def screen_stocks():
    """Screening saham berbasis EMA, Volume Breakout, ATR, dan RSI Filter."""
    signals_count = 0

    for ticker in WATCHLIST:
        try:
            df = yf.download(
                ticker, period="100d", interval="1d", progress=False
            )
            if df.empty or len(df) < 50:
                continue

            close = (
                df["Close"][ticker]
                if isinstance(df.columns, pd.MultiIndex)
                else df["Close"]
            )
            high = (
                df["High"][ticker]
                if isinstance(df.columns, pd.MultiIndex)
                else df["High"]
            )
            low = (
                df["Low"][ticker]
                if isinstance(df.columns, pd.MultiIndex)
                else df["Low"]
            )
            volume = (
                df["Volume"][ticker]
                if isinstance(df.columns, pd.MultiIndex)
                else df["Volume"]
            )

            df_clean = pd.DataFrame(
                {"High": high, "Low": low, "Close": close, "Volume": volume}
            )

            # Indicator Calculations
            ema20 = close.ewm(span=20, adjust=False).mean()
            ema50 = close.ewm(span=50, adjust=False).mean()
            vol_avg20 = volume.rolling(window=20).mean()
            atr = calculate_atr(df_clean, period=14)
            rsi = calculate_rsi(close, period=14)

            last_close = float(close.iloc[-1])
            last_ema20 = float(ema20.iloc[-1])
            last_ema50 = float(ema50.iloc[-1])
            last_vol = float(volume.iloc[-1])
            last_vol_avg = float(vol_avg20.iloc[-1])
            last_atr = float(atr.iloc[-1])
            last_rsi = float(rsi.iloc[-1])

            # Syarat Technical:
            # 1. Uptrend (Close > EMA20 > EMA50)
            # 2. Volume Spike (> Rata-rata 20 Hari)
            # 3. RSI < 70 (Belum Overbought / Belum Pucuk)
            cond_uptrend = (last_close > last_ema20) and (
                last_ema20 > last_ema50
            )
            cond_volume = last_vol > last_vol_avg
            cond_rsi = last_rsi < 70

            if cond_uptrend and cond_volume and cond_rsi:
                signals_count += 1
                ticker_clean = ticker.replace(".JK", "")

                # ATR Dynamic Calculation
                stop_loss = round(last_close - (1.5 * last_atr))
                target_price = round(last_close + (3.0 * last_atr))

                # Hitung Lot
                price_per_lot = last_close * 100
                lots = max(1, int(CAPITAL_PER_POSITION // price_per_lot))
                investment_amt = lots * price_per_lot

                vol_ratio = round(last_vol / last_vol_avg, 2)
                sl_pct = round(((stop_loss - last_close) / last_close) * 100, 1)
                tp_pct = round(
                    ((target_price - last_close) / last_close) * 100, 1
                )

                # Format Pesan Telegram
                caption = f"🚀 *SINYAL SWING TRADING: {ticker_clean}*\n"
                caption += f"-----------------------------------\n"
                caption += f"• Harga Closing: Rp {last_close:,.0f}\n"
                caption += f"• RSI (14): *{last_rsi:.1f}* (Aman < 70)\n"
                caption += f"• Volatilitas (ATR14): Rp {last_atr:,.0f}\n"
                caption += f"• Lonjakan Volume: {vol_ratio}x rata-rata\n\n"
                caption += f"🎯 Target Profit (+{tp_pct}%): *Rp {target_price:,.0f}*\n"
                caption += f"🛡️ Stop Loss ({sl_pct}%): *Rp {stop_loss:,.0f}*\n\n"
                caption += f"🛒 *Beli: {lots} Lot* (~Rp {investment_amt:,.0f})\n"
                caption += f"-----------------------------------\n"
                caption += f"💡 Pasang Automatic Order / GTC sebelum pasar buka besok jam 09.00 WIB."

                # Buat Chart & Kirim ke Telegram
                image_path = generate_chart(df_clean, ticker)
                send_telegram_photo(image_path, caption)

                if os.path.exists(image_path):
                    os.remove(image_path)

        except Exception as e:
            print(f"Error processing {ticker}: {e}")

    return signals_count


def main():
    print("Mengecek tren IHSG...")
    is_bullish = check_ihsg_trend()

    if not is_bullish:
        msg = (
            "⚠️ *IHSG MARKET ALERT*\n"
            "Status Pasar: *BEARISH / SIDEWAYS* (IHSG < MA50).\n\n"
            "🛡️ *Rekomendasi:* NO TRADE / Hold Cash. Bot tidak merekomendasikan posisi baru hari ini."
        )
        send_telegram_text(msg)
        return

    print("Melakukan screening saham...")
    total_signals = screen_stocks()

    if total_signals == 0:
        msg = (
            "📊 *HASIL SCREENING MALAM INI*\n"
            "Status IHSG: *BULLISH*\n\n"
            "Tidak ada saham di watchlist yang memenuhi kriteria $EMA_{20}/EMA_{50}$ + Volume Spike + RSI < 70 hari ini."
        )
        send_telegram_text(msg)


if __name__ == "__main__":
    main()
