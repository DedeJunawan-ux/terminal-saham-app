"""
komponen/candlestick_analyzer.py
=================================
Modul ini menggantikan pendekatan lama dimana AI (Llama 3.3 70B) diminta
MENEBAK nama pola candlestick hanya dari deretan angka OHLCV dalam bentuk
teks. Cara lama itu rawan "halusinasi" -- model bisa menyebut nama pola yang
terdengar masuk akal padahal tidak memenuhi definisi geometris aslinya,
apalagi untuk pola 2-3 candle seperti Morning Star / Three White Soldiers.

Pendekatan baru di modul ini:
1. Pola dideteksi secara MATEMATIS & DETERMINISTIK dari rasio body/wick,
   bukan ditebak oleh LLM. Definisi tiap pola mengikuti konvensi analisis
   teknikal standar (lihat konstanta AMBANG_* di bawah, silakan disetel
   ulang kalau mau lebih ketat/longgar).
2. Tiap pola dapat skor "confidence" 0-100 yang dihitung dari seberapa kuat
   rasio geometrisnya memenuhi kriteria pola tsb, DIKALI faktor konfirmasi
   volume (volume hari itu vs rata-rata 20 hari) dan faktor kedekatan
   dengan support/resistance.
3. AI (lewat Groq) HANYA dipakai untuk menjelaskan makna & implikasi dari
   pola yang sudah pasti terdeteksi -- bukan untuk menentukan pola itu
   sendiri. Ini mengurangi ruang untuk model "mengarang".
4. Tersedia fungsi untuk bikin grafik candlestick interaktif (Plotly) yang
   sudah ditandai lokasi pola yang terdeteksi, support, dan resistance --
   supaya user bisa verifikasi sendiri secara visual, bukan cuma percaya teks.

Sengaja TIDAK pakai TA-Lib / pandas-ta: TA-Lib butuh kompilasi library C
yang sering bermasalah di lingkungan deploy seperti Streamlit Community
Cloud (butuh packages.txt + apt yang kadang gagal). Implementasi di sini
murni pandas/numpy supaya portable.
"""

import numpy as np
import pandas as pd

# ==========================================================
# AMBANG BATAS (THRESHOLD) UNTUK TIAP DEFINISI POLA
# Silakan disetel ulang kalau hasil terasa terlalu sensitif/longgar.
# ==========================================================
AMBANG_DOJI_BODY_PCT       = 0.07   # body <= 7% dari range -> dianggap doji
AMBANG_MARUBOZU_BODY_PCT   = 0.90   # body >= 90% dari range -> marubozu
AMBANG_SPINNING_BODY_PCT   = (0.07, 0.30)
AMBANG_PALU_WICK_RASIO     = 2.0    # wick panjang >= 2x body untuk hammer/shooting star
AMBANG_PALU_WICK_PENDEK    = 0.40   # wick pendek <= 0.4x body
AMBANG_TREN_SLOPE_RELATIF  = 0.0025 # kemiringan regresi linear relatif terhadap harga rata2
LOOKBACK_TREN              = 10     # jumlah candle ke belakang untuk menilai tren
WINDOW_VOLUME              = 20     # window rata-rata volume untuk konfirmasi
ZONA_SR_PERSEN             = 0.025  # 2.5% dari support/resistance dianggap "di area" S/R


def _siapkan_kolom(df: pd.DataFrame) -> pd.DataFrame:
    """Tambah kolom turunan (body, wick, arah, dst) yang dipakai semua detektor."""
    df = df.copy()
    df["body"] = (df["Close"] - df["Open"]).abs()
    df["range"] = (df["High"] - df["Low"]).replace(0, np.nan)
    df["arah"] = np.select(
        [df["Close"] > df["Open"], df["Close"] < df["Open"]],
        ["bullish", "bearish"],
        default="doji",
    )
    df["upper_wick"] = df["High"] - df[["Open", "Close"]].max(axis=1)
    df["lower_wick"] = df[["Open", "Close"]].min(axis=1) - df["Low"]
    df["body_pct"] = (df["body"] / df["range"]).fillna(0.0).clip(0, 1)
    return df


def _deteksi_tren(df: pd.DataFrame, idx: int, lookback: int = LOOKBACK_TREN) -> str:
    """Nilai tren sebelum candle ke-idx pakai kemiringan regresi linear sederhana."""
    mulai = max(0, idx - lookback)
    sub = df["Close"].iloc[mulai:idx]
    if len(sub) < 3:
        return "sideways"
    x = np.arange(len(sub))
    slope = np.polyfit(x, sub.values, 1)[0]
    rerata = sub.mean()
    slope_relatif = slope / rerata if rerata else 0.0
    if slope_relatif > AMBANG_TREN_SLOPE_RELATIF:
        return "uptrend"
    if slope_relatif < -AMBANG_TREN_SLOPE_RELATIF:
        return "downtrend"
    return "sideways"


def _faktor_volume(df: pd.DataFrame, idx: int, window: int = WINDOW_VOLUME) -> float:
    """Rasio volume candle ke-idx terhadap rata-rata `window` candle sebelumnya."""
    mulai = max(0, idx - window)
    if idx <= mulai:
        return 1.0
    rerata_vol = df["Volume"].iloc[mulai:idx].mean()
    if not rerata_vol or np.isnan(rerata_vol) or rerata_vol == 0:
        return 1.0
    return float(df["Volume"].iloc[idx] / rerata_vol)


def _faktor_zona_sr(harga: float, support: float, resistance: float) -> tuple[float, str]:
    """Cek apakah harga sedang berada di area dekat support atau resistance."""
    if support and abs(harga - support) / support <= ZONA_SR_PERSEN:
        return 1.15, "dekat support"
    if resistance and abs(harga - resistance) / resistance <= ZONA_SR_PERSEN:
        return 1.15, "dekat resistance"
    return 1.0, "area netral"


def _skor(nilai_rasio: float, ambang: float, maks_rasio: float, dasar: float = 55.0) -> float:
    """Ubah seberapa jauh suatu rasio melampaui ambang batas jadi skor 0-100."""
    if nilai_rasio < ambang:
        return 0.0
    progres = (nilai_rasio - ambang) / max(maks_rasio - ambang, 1e-6)
    return float(min(100.0, dasar + progres * (100.0 - dasar)))


def _bentuk_palu(row, terbalik: bool = False) -> float:
    """Skor seberapa mirip satu candle dengan bentuk Hammer (atau kebalikannya, Shooting Star)."""
    body = row["body"]
    if body <= 0:
        return 0.0
    wick_panjang = row["lower_wick"] if not terbalik else row["upper_wick"]
    wick_pendek = row["upper_wick"] if not terbalik else row["lower_wick"]
    if wick_panjang < AMBANG_PALU_WICK_RASIO * body:
        return 0.0
    if wick_pendek > AMBANG_PALU_WICK_PENDEK * body:
        return 0.0
    rasio = wick_panjang / body
    return _skor(rasio, AMBANG_PALU_WICK_RASIO, AMBANG_PALU_WICK_RASIO * 3)


def deteksi_pola_candlestick(df: pd.DataFrame, n_terakhir: int = 6) -> list[dict]:
    """
    Pindai `n_terakhir` candle terakhir dari df dan kembalikan daftar pola yang
    SECARA MATEMATIS terdeteksi (bukan tebakan AI), lengkap dengan confidence
    numerik (0-100), arah sinyal, dan konteks (tren & volume).

    Return: list of dict dengan keys:
        tanggal, pola, arah ('bullish'/'bearish'/'netral'),
        confidence (0-100), tren_sebelumnya, info_volume, info_lokasi
    """
    if df.empty or len(df) < 4:
        return []

    df = _siapkan_kolom(df.dropna(how="any", subset=["Open", "High", "Low", "Close"]))
    support = df["Low"].min()
    resistance = df["High"].max()

    hasil = []
    n = len(df)
    mulai_scan = max(2, n - n_terakhir)

    for i in range(mulai_scan, n):
        row = df.iloc[i]
        tanggal = df.index[i]
        tren = _deteksi_tren(df, i)
        vol_faktor = _faktor_volume(df, i)
        sr_faktor, lokasi = _faktor_zona_sr(row["Close"], support, resistance)
        kandidat = []  # (nama_pola, arah, skor_dasar)

        # --- Pola satu candle ---
        if row["body_pct"] <= AMBANG_DOJI_BODY_PCT:
            skor = _skor(AMBANG_DOJI_BODY_PCT - row["body_pct"], 0, AMBANG_DOJI_BODY_PCT, dasar=60)
            kandidat.append(("Doji (indecision)", "netral", skor))

        if AMBANG_SPINNING_BODY_PCT[0] < row["body_pct"] <= AMBANG_SPINNING_BODY_PCT[1] \
                and row["upper_wick"] > row["body"] and row["lower_wick"] > row["body"]:
            kandidat.append(("Spinning Top", "netral", 55.0))

        if row["body_pct"] >= AMBANG_MARUBOZU_BODY_PCT:
            arah = "bullish" if row["arah"] == "bullish" else "bearish"
            nama = "Marubozu Bullish (tekanan beli kuat)" if arah == "bullish" else "Marubozu Bearish (tekanan jual kuat)"
            skor = _skor(row["body_pct"], AMBANG_MARUBOZU_BODY_PCT, 1.0, dasar=65)
            kandidat.append((nama, arah, skor))

        skor_palu = _bentuk_palu(row, terbalik=False)
        if skor_palu > 0:
            if tren == "downtrend":
                kandidat.append(("Hammer", "bullish", skor_palu))
            elif tren == "uptrend":
                kandidat.append(("Hanging Man", "bearish", skor_palu))

        skor_palu_terbalik = _bentuk_palu(row, terbalik=True)
        if skor_palu_terbalik > 0:
            if tren == "downtrend":
                kandidat.append(("Inverted Hammer", "bullish", skor_palu_terbalik))
            elif tren == "uptrend":
                kandidat.append(("Shooting Star", "bearish", skor_palu_terbalik))

        # --- Pola dua candle (butuh candle sebelumnya) ---
        if i >= 1:
            prev = df.iloc[i - 1]

            # Engulfing
            if prev["arah"] == "bearish" and row["arah"] == "bullish" \
                    and row["Open"] <= prev["Close"] and row["Close"] >= prev["Open"] \
                    and row["body"] > prev["body"]:
                rasio = row["body"] / prev["body"] if prev["body"] else 2
                skor = _skor(rasio, 1.0, 2.5, dasar=60)
                kandidat.append(("Bullish Engulfing", "bullish", skor))

            if prev["arah"] == "bullish" and row["arah"] == "bearish" \
                    and row["Open"] >= prev["Close"] and row["Close"] <= prev["Open"] \
                    and row["body"] > prev["body"]:
                rasio = row["body"] / prev["body"] if prev["body"] else 2
                skor = _skor(rasio, 1.0, 2.5, dasar=60)
                kandidat.append(("Bearish Engulfing", "bearish", skor))

            # Harami (kebalikan dari engulfing -- body kecil di dalam body besar sebelumnya)
            batas_atas_prev = max(prev["Open"], prev["Close"])
            batas_bawah_prev = min(prev["Open"], prev["Close"])
            if prev["body_pct"] >= 0.5 and row["body"] < prev["body"] * 0.6 \
                    and batas_bawah_prev <= row["Open"] <= batas_atas_prev \
                    and batas_bawah_prev <= row["Close"] <= batas_atas_prev:
                if prev["arah"] == "bearish":
                    kandidat.append(("Bullish Harami", "bullish", 58.0))
                elif prev["arah"] == "bullish":
                    kandidat.append(("Bearish Harami", "bearish", 58.0))

            # Piercing Line / Dark Cloud Cover
            titik_tengah_prev = (prev["Open"] + prev["Close"]) / 2
            if prev["arah"] == "bearish" and row["arah"] == "bullish" \
                    and row["Open"] < prev["Close"] and titik_tengah_prev < row["Close"] < prev["Open"]:
                kandidat.append(("Piercing Line", "bullish", 60.0))

            if prev["arah"] == "bullish" and row["arah"] == "bearish" \
                    and row["Open"] > prev["Close"] and prev["Open"] < row["Close"] < titik_tengah_prev:
                kandidat.append(("Dark Cloud Cover", "bearish", 60.0))

        # --- Pola tiga candle ---
        if i >= 2:
            c1, c2 = df.iloc[i - 2], df.iloc[i - 1]
            c3 = row
            titik_tengah_c1 = (c1["Open"] + c1["Close"]) / 2

            # Morning Star: turun besar, lalu candle kecil (star), lalu naik besar menutup > tengah c1
            if c1["arah"] == "bearish" and c1["body_pct"] > 0.5 \
                    and c2["body_pct"] < 0.35 \
                    and c3["arah"] == "bullish" and c3["body_pct"] > 0.5 \
                    and c3["Close"] > titik_tengah_c1:
                kandidat.append(("Morning Star", "bullish", 70.0))

            # Evening Star: kebalikannya
            if c1["arah"] == "bullish" and c1["body_pct"] > 0.5 \
                    and c2["body_pct"] < 0.35 \
                    and c3["arah"] == "bearish" and c3["body_pct"] > 0.5 \
                    and c3["Close"] < titik_tengah_c1:
                kandidat.append(("Evening Star", "bearish", 70.0))

            # Three White Soldiers
            if c1["arah"] == "bullish" and c2["arah"] == "bullish" and c3["arah"] == "bullish" \
                    and c2["Close"] > c1["Close"] and c3["Close"] > c2["Close"] \
                    and c1["body_pct"] > 0.5 and c2["body_pct"] > 0.5 and c3["body_pct"] > 0.5 \
                    and c1["Open"] < c2["Open"] < c2["Close"] and c2["Open"] < c3["Open"] < c3["Close"]:
                kandidat.append(("Three White Soldiers", "bullish", 68.0))

            # Three Black Crows
            if c1["arah"] == "bearish" and c2["arah"] == "bearish" and c3["arah"] == "bearish" \
                    and c2["Close"] < c1["Close"] and c3["Close"] < c2["Close"] \
                    and c1["body_pct"] > 0.5 and c2["body_pct"] > 0.5 and c3["body_pct"] > 0.5 \
                    and c1["Open"] > c2["Open"] > c2["Close"] and c2["Open"] > c3["Open"] > c3["Close"]:
                kandidat.append(("Three Black Crows", "bearish", 68.0))

        # Gabungkan kandidat hari ini dengan faktor volume & lokasi S/R jadi confidence akhir
        for nama_pola, arah, skor_dasar in kandidat:
            confidence = skor_dasar
            info_volume = f"volume {vol_faktor:.1f}x rata-rata {WINDOW_VOLUME} hari"
            if vol_faktor >= 1.3:
                confidence = min(100.0, confidence * 1.12)
                info_volume += " (konfirmasi kuat)"
            elif vol_faktor < 0.7:
                confidence = confidence * 0.9
                info_volume += " (lemah, kurang meyakinkan)"
            confidence = min(100.0, confidence * sr_faktor)

            hasil.append({
                "tanggal": tanggal,
                "pola": nama_pola,
                "arah": arah,
                "confidence": round(confidence, 1),
                "tren_sebelumnya": tren,
                "info_volume": info_volume,
                "info_lokasi": lokasi,
            })

    # Urutkan: pola paling baru & paling tinggi confidence-nya di atas
    hasil.sort(key=lambda d: (d["tanggal"], d["confidence"]), reverse=True)
    return hasil


def ringkas_pola_untuk_prompt(pola_terdeteksi: list[dict], support: float, resistance: float) -> str:
    """
    Format hasil deteksi matematis jadi teks ringkas untuk dimasukkan ke prompt AI.
    AI tinggal menjelaskan makna pola ini -- TIDAK diminta menentukan pola dari nol lagi.
    """
    if not pola_terdeteksi:
        return (f"Tidak ada pola candlestick signifikan yang terdeteksi secara matematis "
                f"pada beberapa candle terakhir. Support: {support:,.0f}, Resistance: {resistance:,.0f}.")

    baris = [f"Support: {support:,.0f} | Resistance: {resistance:,.0f}", "Pola yang TERDETEKSI SECARA MATEMATIS (urut dari yang terbaru):"]
    for p in pola_terdeteksi[:6]:
        tgl = p["tanggal"].strftime("%Y-%m-%d") if hasattr(p["tanggal"], "strftime") else str(p["tanggal"])
        baris.append(
            f"- {tgl} | {p['pola']} (sinyal {p['arah']}, confidence {p['confidence']}/100) | "
            f"tren sebelumnya: {p['tren_sebelumnya']} | {p['info_volume']} | lokasi: {p['info_lokasi']}"
        )
    return "\n".join(baris)


def bangun_grafik_candlestick(df: pd.DataFrame, ticker: str, support: float = None,
                               resistance: float = None, pola_terdeteksi: list[dict] = None,
                               jumlah_candle: int = 40):
    """
    Bangun grafik candlestick interaktif (Plotly) bertema gelap selaras dengan UI,
    lengkap dengan garis support/resistance dan anotasi lokasi pola yang terdeteksi.
    Mengembalikan objek plotly.graph_objects.Figure -- tampilkan dengan st.plotly_chart().
    """
    import plotly.graph_objects as go

    df_plot = df.tail(jumlah_candle)

    fig = go.Figure(data=[go.Candlestick(
        x=df_plot.index,
        open=df_plot["Open"], high=df_plot["High"], low=df_plot["Low"], close=df_plot["Close"],
        increasing_line_color="#86efac", increasing_fillcolor="#86efac",
        decreasing_line_color="#fca5a5", decreasing_fillcolor="#fca5a5",
        name=ticker,
    )])

    if support:
        fig.add_hline(y=support, line_dash="dot", line_color="#60a5fa", line_width=1,
                       annotation_text=f"Support {support:,.0f}", annotation_font_color="#93c5fd")
    if resistance:
        fig.add_hline(y=resistance, line_dash="dot", line_color="#f472b6", line_width=1,
                       annotation_text=f"Resistance {resistance:,.0f}", annotation_font_color="#f9a8d4")

    if pola_terdeteksi:
        for p in pola_terdeteksi[:6]:
            if p["tanggal"] not in df_plot.index:
                continue
            y_anchor = df_plot.loc[p["tanggal"], "High"]
            warna = "#86efac" if p["arah"] == "bullish" else ("#fca5a5" if p["arah"] == "bearish" else "#fcd34d")
            fig.add_annotation(
                x=p["tanggal"], y=y_anchor,
                text=f"{p['pola']} ({p['confidence']:.0f}%)",
                showarrow=True, arrowhead=2, arrowcolor=warna, ax=0, ay=-35,
                font=dict(color=warna, size=10),
                bgcolor="rgba(10,0,25,0.85)", bordercolor=warna, borderwidth=1,
            )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(20,0,40,0.35)",
        font=dict(color="#e9d5ff", family="Noto Sans JP, sans-serif"),
        xaxis_rangeslider_visible=False,
        height=460,
        margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(visible=False),
    )
    fig.update_xaxes(gridcolor="rgba(244,114,182,0.08)")
    fig.update_yaxes(gridcolor="rgba(244,114,182,0.08)")
    return fig