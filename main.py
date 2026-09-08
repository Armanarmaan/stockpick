import os
import pandas as pd
import requests
import yfinance as yf

# Ambil Token & Chat ID dari Environment Variables Cloud
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

# Daftar Saham Likuid IHSG (Bisa lo tambah/kurangi sesuai selera)
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

CAPITAL_PER_POSITION = 1500000  # Porsi modal Rp 1.500.000 per saham


def send_telegram(message):
    """Kirim pesan hasil screening ke Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Telegram Token/Chat ID belum di-set. Menampilkan pesan di console:")
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
        print(f"Gagal mengirim pesan ke Telegram: {e}")


def check_ihsg_trend():
    """Modifikasi Filter Pasar: IHSG harus di atas MA50 (Uptrend)."""
    try:
        df = yf.download("^JKSE", period="100d", interval="1d", progress=False)
        if df.empty:
            return False

        close = df["Close"]["^JKSE"] if isinstance(df.columns, pd.MultiIndex) else df["Close"]
        ma50 = close.rolling(window=50).mean()

        return float(close.iloc[-1]) > float(ma50.iloc[-1])
    except Exception as e:
        print(f"Error checking IHSG: {e}")
        return True  # Fallback ke True jika data IHSG error


def screen_stocks():
    """Screening saham berbasis EMA20/EMA50 + Volume Breakout."""
    signals = []

    for ticker in WATCHLIST:
        try:
            df = yf.download(
                ticker, period="100d", interval="1d", progress=False
            )
            if df.empty or len(df) < 50:
                continue

            close = df["Close"][ticker] if isinstance(df.columns, pd.MultiIndex) else df["Close"]
            volume = df["Volume"][ticker] if isinstance(df.columns, pd.MultiIndex) else df["Volume"]

            ema20 = close.ewm(span=20, adjust=False).mean()
            ema50 = close.ewm(span=50, adjust=False).mean()
            vol_avg20 = volume.rolling(window=20).mean()

            last_close = float(close.iloc[-1])
            last_ema20 = float(ema20.iloc[-1])
            last_ema50 = float(ema50.iloc[-1])
            last_vol = float(volume.iloc[-1])
            last_vol_avg = float(vol_avg20.iloc[-1])

            # Syarat 1: Uptrend (Close > EMA20 > EMA50)
            cond_uptrend = (last_close > last_ema20) and (
                last_ema20 > last_ema50
            )
            # Syarat 2: Volume > Volume rata-rata 20 hari
            cond_volume = last_vol > last_vol_avg

            if cond_uptrend and cond_volume:
                target_price = round(last_close * 1.08)  # Target Profit +8%
                stop_loss = round(last_close * 0.96)  # Stop Loss -4%

                # Kalkulasi Lot (1 Lot = 100 lembar)
                price_per_lot = last_close * 100
                lots = max(1, int(CAPITAL_PER_POSITION // price_per_lot))
                investment_amt = lots * price_per_lot

                signals.append({
                    "symbol": ticker.replace(".JK", ""),
                    "close": last_close,
                    "target": target_price,
                    "sl": stop_loss,
                    "lots": lots,
                    "investment": investment_amt,
                    "vol_ratio": round(last_vol / last_vol_avg, 2),
                })
        except Exception as e:
            print(f"Error processing {ticker}: {e}")

    return signals


def main():
    print("Mengecek tren IHSG...")
    is_bullish = check_ihsg_trend()

    if not is_bullish:
        msg = (
            "⚠️ *IHSG MARKET ALERT*\n"
            "Status Pasar: *BEARISH / SIDEWAYS* (IHSG < MA50).\n\n"
            "🛡️ *Rekomendasi:* NO TRADE / Hold Cash. Bot tidak menyarankan eksekusi posisi baru hari ini."
        )
        send_telegram(msg)
        return

    print("Melakukan screening saham...")
    results = screen_stocks()

    if not results:
        msg = "📊 *HASIL SCREENING MALAM INI*\nStatus IHSG: *BULLISH*\n\nTidak ada saham di watchlist yang memenuhi syarat teknikal hari ini."
        send_telegram(msg)
        return

    msg = "🚀 *REKOMENDASI SWING TRADING IHSG* 🚀\n"
    msg += "Status Pasar: *BULLISH* (IHSG > MA50)\n"
    msg += "-----------------------------------\n\n"

    for s in results:
        msg += f"📌 *Saham: {s['symbol']}*\n"
        msg += f"• Harga Closing: Rp {s['close']:,.0f}\n"
        msg += f"• Lonjakan Volume: {s['vol_ratio']}x rata-rata\n"
        msg += f"• Target Profit (+8%): *Rp {s['target']:,.0f}*\n"
        msg += f"• Stop Loss (-4%): *Rp {s['sl']:,.0f}*\n"
        msg += f"• Beli: *{s['lots']} Lot* (~Rp {s['investment']:,.0f})\n"
        msg += "-----------------------------------\n\n"

    msg += "💡 *Instruksi:* Pasang Automatic Order / GTC Buy di aplikasi sekuritas lo besok pagi sebelum jam 09.00 WIB."
    send_telegram(msg)


if __name__ == "__main__":
    main()