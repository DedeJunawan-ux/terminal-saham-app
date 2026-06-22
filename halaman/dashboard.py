import streamlit as st
import yfinance as yf
import pandas as pd
from gnews import GNews
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import pytz
import requests
import os
import re
from komponen.pdf_parser import ambil_metrik_pdf
from komponen.scraper_bursa import ambil_bandarlogi_gratis, hitung_obi_lokal
from komponen.db import (
    simpan_ke_db, ambil_status, set_status, ambil_riwayat_laporan,
    ambil_dompet, setor_deposit, beli_saham, eksekusi_jual, ambil_portofolio
)
from komponen.candlestick_analyzer import (
    deteksi_pola_candlestick, ringkas_pola_untuk_prompt, bangun_grafik_candlestick
)

# CATATAN PENTING:
# st.set_page_config() TIDAK dipanggil di sini lagi. Halaman ini sekarang
# dijalankan sebagai st.Page lewat app.py (pg.run()), dan set_page_config()
# hanya boleh dipanggil sekali per eksekusi script -- itu sudah dilakukan
# di app.py sebagai entry point tunggal. Memanggilnya lagi di sini akan
# menimbulkan StreamlitAPIException.

# ==========================================
# 1. KONFIGURASI VARIABEL & SESI
# ==========================================
count = st_autorefresh(interval=300000, limit=None, key="auto_refresh")

TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]
GROQ_API_KEY = st.secrets["GROQ_API_KEY"]

SAHAM_INVESTASI = ["BBCA.JK", "BBRI.JK", "BMRI.JK", "TLKM.JK", "ASII.JK", "ICBP.JK"]
SAHAM_TRADING = ["BRIS.JK", "ISAT.JK", "GOTO.JK", "ANTM.JK", "PGEO.JK", "ADRO.JK", "MEDC.JK", "BRPT.JK", "AMMN.JK"]
SAHAM_PANTAUAN = SAHAM_INVESTASI + SAHAM_TRADING

zona_wib = pytz.timezone('Asia/Jakarta')
jam_sekarang = datetime.now(zona_wib).strftime("%Y-%m-%d-%H")

if 'laporan_terakhir' not in st.session_state:
    st.session_state['laporan_terakhir'] = "Menunggu data pasar..."
if 'memori_chat' not in st.session_state:
    st.session_state['memori_chat'] = []

# ==========================================
# 2. CSS ANIME THEME & PERBAIKAN UI
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Zen+Kaku+Gothic+New:wght@300;400;700;900&family=Noto+Sans+JP:wght@300;400;700&family=M+PLUS+Rounded+1c:wght@300;400;700;800&family=Kosugi+Maru&display=swap');

    .viewerBadge_container, .viewerBadge_link { display: none !important; }

    header[data-testid="stHeader"] { background: transparent !important; z-index: 99999 !important; }
    [data-testid="collapsedControl"] {
        z-index: 999999 !important;
        background-color: rgba(244, 114, 182, 0.15) !important;
        border: 1px solid rgba(244, 114, 182, 0.4) !important;
        border-radius: 8px !important; margin: 15px !important;
    }
    [data-testid="collapsedControl"] svg { fill: #f9a8d4 !important; color: #f9a8d4 !important; }

    .block-container { padding-top: 3rem !important; padding-bottom: 2rem !important; max-width: 99% !important; }

    [data-testid="stExpander"] { background: rgba(20, 0, 40, 0.4) !important; border: 1px solid rgba(244, 114, 182, 0.3) !important; border-radius: 10px !important; }
    [data-testid="stExpander"] summary { color: #f9a8d4 !important; font-weight: bold !important; }

    button[data-baseweb="tab"] { font-size: 14px !important; font-weight: 700 !important; color: rgba(233, 213, 255, 0.6) !important; }
    button[data-baseweb="tab"][aria-selected="true"] { color: #f9a8d4 !important; border-bottom-color: #f9a8d4 !important; background-color: rgba(244, 114, 182, 0.05) !important; border-radius: 8px 8px 0 0 !important; }
    @media (max-width: 768px) { button[data-baseweb="tab"] { font-size: 12px !important; padding-left: 10px !important; padding-right: 10px !important; } }

    @keyframes sakuraFall { 0% { transform: translate(0, -20px) rotate(0deg); opacity: 0; } 10% { opacity: 0.8; } 90% { opacity: 0.6; } 100% { transform: translate(30px, 110vh) rotate(720deg); opacity: 0; } }
    @keyframes sakuraFall2 { 0% { transform: translate(0, -20px) rotate(0deg); opacity: 0; } 10% { opacity: 0.7; } 100% { transform: translate(-40px, 110vh) rotate(-540deg); opacity: 0; } }
    @keyframes glowPulse { 0%, 100% { box-shadow: 0 0 10px rgba(255, 105, 180, 0.3), 0 0 20px rgba(147, 51, 234, 0.1); } 50% { box-shadow: 0 0 20px rgba(255, 105, 180, 0.6), 0 0 40px rgba(147, 51, 234, 0.3); } }
    @keyframes fadeSlideUp { from { opacity: 0; transform: translateY(24px); } to { opacity: 1; transform: translateY(0); } }
    @keyframes orb { 0% { transform: translate(0, 0) scale(1); } 33% { transform: translate(30px, -20px) scale(1.1); } 66% { transform: translate(-20px, 10px) scale(0.9); } 100% { transform: translate(0, 0) scale(1); } }

    html, body { background: #0a0015 !important; }
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"], section.main, .main .block-container { background: linear-gradient(160deg, #0a0015 0%, #120025 25%, #0d001a 50%, #020010 75%, #080018 100%) !important; color: #f0e6ff !important; font-family: 'Noto Sans JP', sans-serif !important; }

    .stApp::before { content: ''; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: radial-gradient(ellipse at 10% 15%, rgba(255, 105, 180, 0.08) 0%, transparent 40%), radial-gradient(ellipse at 90% 80%, rgba(138, 43, 226, 0.1) 0%, transparent 40%), radial-gradient(ellipse at 50% 50%, rgba(75, 0, 130, 0.05) 0%, transparent 60%); pointer-events: none; z-index: 0; animation: orb 20s ease-in-out infinite; }

    .sakura-wrap { position: fixed; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 1; overflow: hidden; }
    .petal { position: absolute; top: -30px; font-size: 18px; opacity: 0; animation: sakuraFall linear infinite; filter: drop-shadow(0 0 4px rgba(255,105,180,0.5)); }
    .petal:nth-child(1)  { left: 5%;   animation-duration: 9s;  animation-delay: 0s;    font-size: 14px; }
    .petal:nth-child(2)  { left: 15%;  animation-duration: 12s; animation-delay: 2s;    }
    .petal:nth-child(3)  { left: 28%;  animation-duration: 8s;  animation-delay: 5s;    font-size: 12px; animation-name: sakuraFall2; }
    .petal:nth-child(4)  { left: 40%;  animation-duration: 14s; animation-delay: 1s;    font-size: 20px; }
    .petal:nth-child(5)  { left: 55%;  animation-duration: 10s; animation-delay: 7s;    font-size: 11px; animation-name: sakuraFall2; }

    section[data-testid="stSidebar"] { background: linear-gradient(180deg, #110020 0%, #0d0018 60%, #080012 100%) !important; border-right: 1px solid rgba(244, 114, 182, 0.2) !important; box-shadow: 4px 0 30px rgba(147, 51, 234, 0.15); }
    section[data-testid="stSidebar"] * { color: #e9d5ff !important; }

    div[data-testid="metric-container"] { background: linear-gradient(135deg, rgba(30, 0, 60, 0.9) 0%, rgba(20, 0, 40, 0.95) 100%) !important; border: 1px solid rgba(244, 114, 182, 0.3) !important; border-radius: 16px !important; padding: 20px !important; position: relative; overflow: hidden; animation: glowPulse 3s ease-in-out infinite, fadeSlideUp 0.6s ease forwards; transition: all 0.4s ease; }
    div[data-testid="metric-container"]:hover { transform: translateY(-6px) scale(1.03); border-color: rgba(244, 114, 182, 0.7) !important; box-shadow: 0 12px 40px rgba(244, 114, 182, 0.25), 0 0 60px rgba(147, 51, 234, 0.1); }
    div[data-testid="metric-container"] label { color: rgba(244, 114, 182, 0.7) !important; font-size: 10px !important; letter-spacing: 3px !important; }
    div[data-testid="metric-container"] [data-testid="stMetricValue"] { color: #fdf2ff !important; font-size: 1.5rem !important; font-weight: 800 !important; }

    .anime-hero { text-align: center; margin-bottom: 2rem; animation: fadeSlideUp 1s ease forwards; z-index: 2; position: relative; }
    .anime-title-jp { font-size: 3.2rem; font-weight: 800; background: linear-gradient(135deg, #f9a8d4 0%, #c084fc 40%, #818cf8 70%, #f9a8d4 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; filter: drop-shadow(0 0 20px rgba(244, 114, 182, 0.3)); }
    .anime-title-id { font-size: 0.9rem; letter-spacing: 8px; color: rgba(196, 181, 253, 0.7); }
    .anime-meta-row { display: flex; justify-content: center; gap: 16px; flex-wrap: wrap; margin-top: 14px; }
    .anime-pill { font-size: 10px; letter-spacing: 2px; padding: 6px 16px; border-radius: 50px; border: 1px solid rgba(244, 114, 182, 0.3); background: rgba(244, 114, 182, 0.05); color: rgba(249, 168, 212, 0.8); }

    .anime-terminal { background: linear-gradient(135deg, rgba(10, 0, 25, 0.95), rgba(15, 0, 35, 0.98)); border: 1px solid rgba(244, 114, 182, 0.2); border-radius: 20px; box-shadow: 0 8px 40px rgba(147, 51, 234, 0.2); animation: glowPulse 5s ease-in-out infinite; }
    .anime-terminal-header { background: linear-gradient(90deg, rgba(244, 114, 182, 0.08), rgba(168, 85, 247, 0.08)); border-bottom: 1px solid rgba(244, 114, 182, 0.15); padding: 12px 20px; display: flex; align-items: center; gap: 10px; font-size: 10px; color: rgba(249, 168, 212, 0.6); }
    .anime-terminal-body { padding: 24px; font-size: 13px; line-height: 2; color: #d8b4fe; white-space: pre-wrap; }
    .anime-terminal-body::before { content: '> '; color: #f472b6; font-weight: bold; }
</style>

<div class="sakura-wrap">
    <div class="petal">🌸</div><div class="petal">🌸</div><div class="petal">🌸</div>
    <div class="petal">🌸</div><div class="petal">🌸</div>
</div>
""", unsafe_allow_html=True)

# ==========================================
# HERO HEADER ANIME
# ==========================================
waktu_sekarang = datetime.now(zona_wib).strftime("%d.%m.%Y // %H:%M:%S WIB")
st.markdown(f"""
<div class="anime-hero">
    <h1 class="anime-title-jp">TERMINAL SAHAM</h1>
    <p class="anime-title-id">TERMINAL SAHAM PROTOKOL  //  ANALISIS KUANTITATIF</p>
    <div class="anime-meta-row">
        <span class="anime-pill">SIARAN LANGSUNG</span>
        <span class="anime-pill">{waktu_sekarang}</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ==========================================
# 3. FUNGSI LOGIKA BURSA & AI
# ==========================================
def kirim_telegram(pesan):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": pesan, "parse_mode": "Markdown"}
    try: requests.post(url, json=payload, timeout=10)
    except Exception: pass

def hitung_indikator(df):
    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['MACDs'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACDh'] = df['MACD'] - df['MACDs']
    delta = df['Close'].diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=13, adjust=False).mean()
    ema_down = down.ewm(com=13, adjust=False).mean()
    rs = ema_up / ema_down
    df['RSI_14'] = 100 - (100 / (1 + rs))
    return df

@st.cache_data(ttl=300, show_spinner=False)
def ambil_data_saham(ticker):
    saham = yf.Ticker(ticker)
    df = saham.history(period="1mo", auto_adjust=True)
    if not df.empty: df = hitung_indikator(df)
    return df

@st.cache_data(ttl=3600, show_spinner=False)
def ambil_fundamental(ticker):
    try:
        saham = yf.Ticker(ticker)
        info = saham.info
        pbv = info.get('priceToBook', 0)
        per = info.get('trailingPE', 0)
        return pbv if pbv else 0, per if per else 0
    except Exception: return 0, 0

@st.cache_data(ttl=120, show_spinner=False)
def ambil_harga_terkini(ticker, fallback):
    """
    Ambil harga pasar terkini untuk satu ticker, dipakai khusus untuk
    menghitung nilai portofolio & P/L di tab Dompet.

    Sebelumnya kode lama langsung pakai yf.Ticker(ticker).info.get('currentPrice', ...)
    -- field 'currentPrice' itu kadang kosong/None karena perubahan di sisi
    Yahoo Finance, sehingga nilai portofolio bisa diam-diam salah tanpa error.

    Fungsi ini coba 3 sumber berurutan, baru menyerah ke harga fallback
    (harga rata-rata beli) kalau semuanya gagal -- supaya tampilan tidak
    pernah kosong/None, tapi juga tidak diam-diam memakai data yang salah.
    """
    try:
        fi = yf.Ticker(ticker).fast_info
        for key in ("last_price", "lastPrice", "regularMarketPrice"):
            try:
                nilai = fi[key]
            except Exception:
                nilai = getattr(fi, key, None)
            if nilai:
                return float(nilai)
    except Exception:
        pass

    try:
        df = yf.Ticker(ticker).history(period="5d")
        if not df.empty:
            return float(df['Close'].iloc[-1])
    except Exception:
        pass

    return fallback

@st.cache_data(ttl=300, show_spinner=False)
def ambil_berita(ticker):
    try:
        gn = GNews(language='id', country='ID', max_results=2)
        hasil = gn.get_news(ticker.replace(".JK", "") + " saham")
        return hasil[0]['title'] if hasil else "-"
    except Exception: return "-"

@st.cache_data(ttl=300, show_spinner=False)
def ambil_berita_makro():
    try:
        gn = GNews(language='id', country='ID', max_results=3)
        hasil = gn.get_news("ihsg ekonomi inflasi")
        return "\n".join([f"- {b['title']}" for b in hasil]) if hasil else "-"
    except Exception: return "-"

@st.cache_data(ttl=300, show_spinner=False)
def ambil_berita_emiten_lengkap(ticker):
    try:
        gn = GNews(language='id', country='ID', max_results=5)
        return gn.get_news(ticker.replace(".JK", "") + " saham")
    except Exception: return []

@st.cache_data(ttl=300, show_spinner=False)
def ambil_berita_makro_lengkap():
    try:
        gn = GNews(language='id', country='ID', max_results=6)
        return gn.get_news("ekonomi geopolitik inflasi bursa ihsg")
    except Exception: return []

def nama_file_pdf_aman(ticker):
    """
    Sanitasi ticker sebelum dipakai sebagai nama file PDF.
    Hanya menyisakan huruf & angka, supaya input ticker yang aneh-aneh
    (mis. mengandung '../') tidak bisa dipakai untuk membentuk path
    di luar folder data_laporan/.
    """
    bersih = ticker.lower().replace(".jk", "")
    bersih = re.sub(r'[^a-z0-9]', '', bersih)
    return f"data_laporan/laporan_{bersih}.pdf"

def analisis_ai_semua(data_saham_list, makro, konteks_pdf, konteks_bandar, konteks_obi):
    ringkasan_investasi = ""
    ringkasan_trading = ""
    for d in data_saham_list:
        baris = f"TICKER: {d['ticker']} | HARGA: {d['harga']:,.0f} | RSI: {d['rsi']:.1f} | MACD: {d['macd']:.4f} | SINYAL: {d['sinyal']} | INFO: {d['berita']}\n"
        if d['kategori'] == "INVESTASI": ringkasan_investasi += baris
        else: ringkasan_trading += baris

    prompt = f"""Kamu adalah sistem AI untuk analisis pasar saham Indonesia. DILARANG KERAS MENGGUNAKAN EMOTIKON/EMOJI.

DATA MAKRO:
{makro}

DATA INVESTASI:
{ringkasan_investasi}

DATA TRADING:
{ringkasan_trading}

[ DATA TAMBAHAN MANDIRI - GRATIS ]
- ANALISIS FUNDAMENTAL (PDF): {konteks_pdf}
- PERGERAKAN BANDAR (EOD): {konteks_bandar}
- KEKUATAN ANTREAN (OBI): {konteks_obi}

Format Laporan:
[ ALOKASI INVESTASI ]
- TICKER (BUY/HOLD/SELL): Alasan ringkas (berdasarkan teknikal dan PDF fundamental).

[ ALOKASI TRADING ]
- TICKER (BUY/HOLD/SELL): Alasan ringkas (berdasarkan teknikal dan bandar/OBI).

[ STATUS SISTEM & PASAR ]
Satu kalimat konklusi pasar.

PENTING: Di baris paling bawah tuliskan "Ini adalah analisis komputasi otomatis, bukan rekomendasi finansial resmi. Keputusan investasi sepenuhnya tanggung jawab pengguna." """

    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 1000
    }
    r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=40)
    if r.status_code == 200: return r.json()["choices"][0]["message"]["content"]
    raise Exception(f"Groq error {r.status_code}: {r.text}")

@st.cache_data(ttl=300, show_spinner=False)
def analisis_candlestick_ai(ticker):
    """
    VERSI BARU: pola candlestick dideteksi SECARA MATEMATIS lebih dulu lewat
    komponen.candlestick_analyzer (rasio body/wick yang presisi, bukan
    tebakan), baru hasil deteksi itu dikirim ke AI hanya untuk dijelaskan
    maknanya & diberi rekomendasi -- AI tidak lagi diminta menentukan nama
    pola dari nol.

    Di-cache 5 menit per ticker supaya klik berulang pada ticker yang sama
    tidak memanggil Groq API & menarik data yfinance berkali-kali sia-sia.

    Return: (df_harga, daftar_pola_terdeteksi, teks_analisis_ai)
    """
    saham = yf.Ticker(ticker)
    df = saham.history(period="3mo")
    if df.empty:
        return None, [], "Gagal menarik data bursa."

    pola_terdeteksi = deteksi_pola_candlestick(df)
    support = df['Low'].min()
    resistance = df['High'].max()
    konteks_pola = ringkas_pola_untuk_prompt(pola_terdeteksi, support, resistance)

    df_14 = df.tail(14)
    data_text = "DATA OHLCV 14 HARI TERAKHIR (untuk konteks tambahan):\n"
    for index, row in df_14.iterrows():
        tanggal = index.strftime('%Y-%m-%d')
        data_text += f"{tanggal} | O: {row['Open']:.0f} | H: {row['High']:.0f} | L: {row['Low']:.0f} | C: {row['Close']:.0f} | Vol: {row['Volume']}\n"

    prompt = f"""Kamu adalah Technical Analyst ahli candlestick patterns dengan pengalaman 15 tahun.
DILARANG MENGGUNAKAN EMOJI.

PENTING -- BACA DULU: Pola candlestick di bawah ini SUDAH TERDETEKSI SECARA
MATEMATIS oleh sistem deteksi berbasis rasio body/wick (bukan tebakanmu).
TUGASMU HANYA menjelaskan makna, konteks, dan implikasinya -- JANGAN
menyebutkan nama pola lain yang tidak ada di daftar ini, dan jangan
membantah hasil deteksi yang sudah diberikan.

{konteks_pola}

Data mentah pendukung (untuk konteks tambahan saja):
{data_text}

Output harus dalam bahasa Indonesia, struktur jelas:

[ ANALISIS CANDLESTICK {ticker} ]
- Pola yang terdeteksi: (sebutkan ulang pola dari daftar di atas, jangan menambah pola baru)
- Penjelasan pola: ...
- Konteks tren & volume: (gunakan info tren/volume yang sudah diberikan di atas)
- Implikasi pergerakan: ...
- Rekomendasi teknikal: Strong Buy / Buy / Hold / Sell / Strong Sell
- Confidence Level: (gunakan confidence numerik yang sudah dihitung sistem di atas, jangan mengarang angka baru)
- Alasan utama: ...

PENTING: Di baris paling bawah tuliskan "Ini hanya analisis teknikal komputasi, bukan financial advice."
"""
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": prompt}], "temperature": 0.2, "max_tokens": 1000}

    try:
        r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=30)
        if r.status_code == 200:
            teks = r.json()["choices"][0]["message"]["content"]
        else:
            teks = f"Error API: {r.status_code}"
    except Exception as e:
        teks = f"Gagal koneksi AI: {e}"

    return df, pola_terdeteksi, teks

# ==========================================
# 4. SIDEBAR & LOGOUT
# ==========================================
with st.sidebar:
    st.markdown("""<div style='text-align:center; padding-top:20px;'><p style='font-size:22px; font-weight:800; color:#f9a8d4;'>CONTROL PANEL</p></div>""", unsafe_allow_html=True)

    st.markdown(f"👤 **{st.session_state.get('username', 'User')}**")
    if st.button("Logout", type="secondary"):
        st.session_state['logged_in'] = False
        st.session_state['username'] = ''
        st.rerun()
    st.divider()

    st.markdown("""
    <div style="background: linear-gradient(135deg, rgba(37, 99, 235, 0.1), rgba(29, 78, 216, 0.3)); border: 1px solid rgba(59, 130, 246, 0.5); padding: 15px; border-radius: 12px; text-align: center; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(37, 99, 235, 0.2);">
        <h4 style="color: #93c5fd; margin: 0 0 5px 0; font-size: 14px; letter-spacing: 1px;">Asisten Telegram</h4>
        <p style="color: #bfdbfe; font-size: 11px; margin: 0 0 12px 0; line-height: 1.4;">Dapatkan notifikasi AI & sinyal pasar langsung ke genggaman Anda.</p>
        <a href="https://t.me/dede_saham_bot" target="_blank" style="background: #3b82f6; color: white; padding: 8px 16px; border-radius: 20px; text-decoration: none; font-size: 12px; font-weight: bold; display: inline-block; transition: all 0.3s; border: 1px solid #60a5fa;">Hubungkan @dede_saham_bot</a>
    </div>
    """, unsafe_allow_html=True)

    st.success("STATUS AI: AKTIF")
    st.success("DATABASE: TERHUBUNG")
    st.info(f"SIKLUS TERAKHIR: {ambil_status('jam_terakhir_kirim', 'MENUNGGU')}")

    st.divider()
    ticker_input = st.text_input("TICKER", "BBRI.JK").upper()
    periode_input = st.selectbox("RENTANG GRAFIK", ["1mo", "3mo", "6mo", "1y"], index=1)
    st.markdown("<br>", unsafe_allow_html=True)

    wadah_tombol_manual = st.empty()

# ==========================================
# 5. PENGUMPULAN DATA BURSA
# ==========================================
data_saham = []
hasil_screener_investasi = []
hasil_screener_trading = []
hasil_screener_value = []

with st.spinner("... Menarik Data Bursa... "):
    for s in SAHAM_PANTAUAN:
        df = ambil_data_saham(s)
        if not df.empty:
            df_b = df.dropna()
            if not df_b.empty:
                harga = df_b['Close'].iloc[-1]
                rsi   = df_b['RSI_14'].iloc[-1]
                macd  = df_b['MACDh'].iloc[-1]
                kat   = "INVESTASI" if s in SAHAM_INVESTASI else "TRADING"
                sinyal = "HOLD"
                berita = "-"

                pbv, per = ambil_fundamental(s)

                if rsi < 30 and macd > 0:
                    sinyal = "STRONG BUY"
                    berita = ambil_berita(s)
                elif rsi < 30:
                    sinyal = "BUY"
                    berita = ambil_berita(s)
                elif rsi > 70:
                    sinyal = "SELL"
                    berita = ambil_berita(s)

                item_data = {"ticker": s, "harga": harga, "rsi": rsi, "macd": macd, "berita": berita, "sinyal": sinyal, "kategori": kat}
                data_saham.append(item_data)

                item_tabel = {"TICKER": s, "HARGA": round(harga, 0), "RSI": round(rsi, 2), "MACD": round(macd, 4), "SINYAL": sinyal}
                if kat == "INVESTASI":
                    hasil_screener_investasi.append(item_tabel)
                else:
                    hasil_screener_trading.append(item_tabel)

                if 0 < pbv < 1.5 and 0 < per < 15 and rsi < 45:
                    item_value = {"TICKER": s, "HARGA": round(harga, 0), "PBV": round(pbv, 2), "PER": round(per, 2), "RSI": round(rsi, 2)}
                    hasil_screener_value.append(item_value)

    makro = ambil_berita_makro()

# ==========================================
# 6. TOMBOL MANUAL & EKSEKUSI AI OTOMATIS
# ==========================================
with wadah_tombol_manual:
    if st.button("LAPORAN MANUAL", type="primary", use_container_width=True):
        with st.spinner("AI ... Mengkalkulasi Data & PDF..."):
            try:
                jalur_pdf = nama_file_pdf_aman(ticker_input)

                k_pdf = ambil_metrik_pdf(jalur_pdf) if os.path.exists(jalur_pdf) else f"Laporan PDF {ticker_input} belum diunggah."
                k_bandar = ambil_bandarlogi_gratis(ticker_input)
                # CATATAN: angka 1.500.000 / 1.000.000 di bawah ini MASIH CONTOH TETAP,
                # bukan volume bid/offer asli dari order book ticker_input. Ditandai
                # eksplisit di teks supaya AI tidak menganggapnya data real-time.
                k_obi = hitung_obi_lokal(1500000, 1000000) + " [CATATAN: volume bid/offer contoh tetap, belum terhubung order book real-time]"

                hasil_ai = analisis_ai_semua(data_saham, makro, k_pdf, k_bandar, k_obi)

                st.session_state['laporan_terakhir'] = hasil_ai
                waktu_str = datetime.now(zona_wib).strftime("%d/%m/%Y %H:%M WIB")
                simpan_ke_db(waktu_str, hasil_ai)
                pesan = f"[ TRANSMISI MANUAL ]\nWAKTU: {waktu_str}\n\n{hasil_ai}"
                if len(pesan) > 4096: pesan = pesan[:4090] + "..."
                kirim_telegram(pesan)
                st.success("TRANSMISI BERHASIL")
            except Exception as e:
                st.error(f"KEGAGALAN: {e}")

# CATATAN PERBAIKAN ARSITEKTUR:
# Sebelumnya status "jam terakhir kirim" disimpan di st.session_state, yang
# bersifat PER-SESI BROWSER. Karena Streamlit menjalankan ulang script untuk
# tiap sesi, kalau ada beberapa user membuka dashboard bersamaan, masing-masing
# sesi akan memicu panggilan Groq API + kirim Telegram sendiri-sendiri setiap
# jam berganti -- alias laporan & biaya API terduplikasi sebanyak jumlah sesi
# yang sedang terbuka.
#
# Sekarang status itu disimpan di tabel status_sistem (lewat ambil_status /
# set_status di komponen/db.py), jadi statusnya GLOBAL untuk seluruh aplikasi,
# bukan per-browser. Auto-report hanya terkirim sekali per jam meskipun ada
# banyak user yang sedang membuka dashboard.
if ambil_status('jam_terakhir_kirim') != jam_sekarang and data_saham:
    try:
        jalur_pdf_auto = nama_file_pdf_aman(ticker_input)
        k_pdf_auto = ambil_metrik_pdf(jalur_pdf_auto) if os.path.exists(jalur_pdf_auto) else f"Laporan PDF {ticker_input} belum diunggah."
        k_bandar_auto = ambil_bandarlogi_gratis(ticker_input)
        k_obi_auto = hitung_obi_lokal(1500000, 1000000) + " [CATATAN: volume bid/offer contoh tetap, belum terhubung order book real-time]"

        hasil_ai = analisis_ai_semua(data_saham, makro, k_pdf_auto, k_bandar_auto, k_obi_auto)
        st.session_state['laporan_terakhir'] = hasil_ai
        waktu_str = datetime.now(zona_wib).strftime("%d/%m/%Y %H:%M WIB")
        simpan_ke_db(waktu_str, hasil_ai)
        pesan = f"[ TRANSMISI SISTEM ]\nWAKTU: {waktu_str}\n\n{hasil_ai}\n\nTerminal Saham Protokol V.4"
        if len(pesan) > 4096: pesan = pesan[:4090] + "..."
        kirim_telegram(pesan)
        set_status('jam_terakhir_kirim', jam_sekarang)
    except Exception:
        pass

# ==========================================
# 7. TAB UTAMA & UI
# ==========================================
tab_screener, tab_riset, tab_ai, tab_dompet = st.tabs(["RADAR PORTOFOLIO", "ANALISIS SPESIFIK", "TANYA AI", "DOMPET & PORTO"])

with tab_screener:
    st.caption(f"Data harga, indikator, dan berita di bawah ini disegarkan otomatis tiap 5 menit. Terakhir disegarkan: {waktu_sekarang}")
    kol_inv, col_trd = st.columns(2)

    with kol_inv:
        st.markdown('<p style="color:#f9a8d4; font-weight:bold;">INVESTASI UTAMA</p>', unsafe_allow_html=True)
        if hasil_screener_investasi: st.dataframe(pd.DataFrame(hasil_screener_investasi), use_container_width=True, hide_index=True)

        st.markdown('<p style="color:#c084fc; font-weight:bold; margin-top:20px;">DEEP VALUE SWING // SAHAM MURAH POTENSI TRADING</p>', unsafe_allow_html=True)
        if hasil_screener_value: st.dataframe(pd.DataFrame(hasil_screener_value), use_container_width=True, hide_index=True)
        else: st.info("Saat ini tidak ada emiten yang memenuhi kriteria Deep Value Swing (PBV < 1.5, PER < 15, RSI < 45).")

    with col_trd:
        st.markdown('<p style="color:#f9a8d4; font-weight:bold;">TRADING AKTIF</p>', unsafe_allow_html=True)
        if hasil_screener_trading: st.dataframe(pd.DataFrame(hasil_screener_trading), use_container_width=True, hide_index=True)

    st.markdown('<p style="color:#f9a8d4; font-weight:bold; margin-top:20px;">AI OUTPUT</p>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="anime-terminal">
        <div class="anime-terminal-header">
            <span style="color:#f9a8d4;">●</span> <span style="color:#fcd34d;">●</span> <span style="color:#86efac;">●</span>
            <span style="margin-left:10px;">AI_ENGINE  //  GROQ × LLAMA-3.3-70B  //  OUTPUT</span>
        </div>
        <div class="anime-terminal-body">{st.session_state['laporan_terakhir']}</div>
    </div>
    """, unsafe_allow_html=True)

with tab_riset:
    df_saham_riset = ambil_data_saham(ticker_input)
    if not df_saham_riset.empty:
        df_b = df_saham_riset.dropna()
        harga = df_b['Close'].iloc[-1]
        perubahan = harga - df_b['Close'].iloc[-2]
        rsi = df_b['RSI_14'].iloc[-1]
        macd = df_b['MACDh'].iloc[-1]

        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("NILAI TRANSAKSI (IDR)", f"Rp {harga:,.0f}", f"{perubahan:+,.0f}")
        col_m2.metric("RSI", f"{rsi:.2f}")
        col_m3.metric("MACD", f"{macd:.4f}")
        st.caption(f"Terakhir disegarkan: {waktu_sekarang}")

        saham_grafik = yf.Ticker(ticker_input)
        df_periode = saham_grafik.history(period=periode_input)
        if not df_periode.empty: st.line_chart(df_periode.dropna()['Close'], use_container_width=True, color="#f472b6")

        with st.expander("BUKA FEED EMITEN TERBARU", expanded=False):
            berita_e_lengkap = ambil_berita_emiten_lengkap(ticker_input)
            if berita_e_lengkap:
                for artikel in berita_e_lengkap: st.markdown(f"❀  [{artikel['title']}]({artikel['url']})")
            else: st.info("Tidak ada data terdeteksi.")

        with st.expander("BUKA FEED MAKROEKONOMI", expanded=False):
            berita_m_lengkap = ambil_berita_makro_lengkap()
            if berita_m_lengkap:
                for artikel in berita_m_lengkap: st.markdown(f"❀  [{artikel['title']}]({artikel['url']})")
            else: st.info("Tidak ada data terdeteksi.")

        st.divider()
        st.markdown('<p style="color:#c084fc; font-weight:bold; font-size:18px;">DETEKSI POLA CANDLESTICK (AI)</p>', unsafe_allow_html=True)

        if st.button(f"Pindai Candlestick {ticker_input}", type="primary", use_container_width=True):
            with st.spinner(f"AI sedang memindai formasi candle {ticker_input} (14 hari terakhir)..."):
                df_candle, pola_terdeteksi, hasil_candle = analisis_candlestick_ai(ticker_input)

                if df_candle is not None:
                    support_candle = df_candle['Low'].min()
                    resistance_candle = df_candle['High'].max()
                    fig_candle = bangun_grafik_candlestick(
                        df_candle, ticker_input,
                        support=support_candle, resistance=resistance_candle,
                        pola_terdeteksi=pola_terdeteksi
                    )
                    st.plotly_chart(fig_candle, use_container_width=True)

                st.markdown(f"""
                <div class="anime-terminal">
                    <div class="anime-terminal-header">
                        <span style="color:#f9a8d4;">●</span> <span style="color:#fcd34d;">●</span> <span style="color:#86efac;">●</span>
                        <span style="margin-left:10px;">AI_PATTERN_RECOGNITION  //  {ticker_input}</span>
                    </div>
                    <div class="anime-terminal-body">{hasil_candle}</div>
                </div>
                """, unsafe_allow_html=True)

                # Simpan riwayat analisis candlestick ke tabel yang sama
                # dengan laporan AI utama (lewat simpan_ke_db), supaya user bisa
                # melacak balik apakah rekomendasi candlestick dulu akhirnya
                # benar atau tidak. Diberi label [CANDLESTICK-TICKER] di
                # kolom waktu supaya bisa dibedakan dari laporan alokasi portofolio.
                try:
                    waktu_candle = datetime.now(zona_wib).strftime("%d/%m/%Y %H:%M WIB")
                    simpan_ke_db(f"[CANDLESTICK-{ticker_input}] {waktu_candle}", hasil_candle)
                except Exception:
                    pass

        with st.expander(f"RIWAYAT ANALISIS CANDLESTICK {ticker_input}", expanded=False):
            try:
                riwayat = ambil_riwayat_laporan(limit=10, filter_like=f"[CANDLESTICK-{ticker_input}]%")
            except Exception:
                riwayat = []
            if riwayat:
                for entri in riwayat:
                    label_waktu = entri["waktu"].replace(f"[CANDLESTICK-{ticker_input}] ", "")
                    st.markdown(f"**{label_waktu}**")
                    st.markdown(f"<div class='anime-terminal-body' style='padding:10px 0;'>{entri['laporan']}</div>", unsafe_allow_html=True)
                    st.divider()
            else:
                st.info("Belum ada riwayat analisis candlestick untuk ticker ini.")
    else: st.error("GAGAL MENGAKSES DATA — Periksa kode ticker.")

with tab_ai:
    st.markdown('<p style="color:#f9a8d4; font-weight:bold;">TERMINAL KOMUNIKASI AI</p>', unsafe_allow_html=True)

    kotak_chat = st.container(height=350)
    with kotak_chat:
        for pesan in st.session_state['memori_chat']:
            with st.chat_message(pesan["role"]): st.markdown(pesan["content"])

    with st.form("form_chat", clear_on_submit=True):
        col_input, col_btn = st.columns([5, 1])
        with col_input: prompt_user = st.text_input("Pesan", label_visibility="collapsed", placeholder="Ketik pertanyaan tentang saham...")
        with col_btn: submit_chat = st.form_submit_button("Kirim", use_container_width=True)

    if submit_chat and prompt_user:
        st.session_state['memori_chat'].append({"role": "user", "content": prompt_user})

        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        pesan_api = [{"role": "system", "content": "Kamu asisten AI ahli pasar modal. Jawab dengan gaya profesional, ringkas, dan bernada cyberpunk/hacker. Jangan gunakan emoji."}]
        pesan_api.extend(st.session_state['memori_chat'])
        payload = {"model": "llama-3.3-70b-versatile", "messages": pesan_api, "temperature": 0.5, "max_tokens": 1000}
        try:
            r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=30)
            if r.status_code == 200:
                st.session_state['memori_chat'].append({"role": "assistant", "content": r.json()["choices"][0]["message"]["content"]})
            else: st.session_state['memori_chat'].append({"role": "assistant", "content": f"Koneksi AI Terputus: {r.status_code}"})
        except Exception as e: st.session_state['memori_chat'].append({"role": "assistant", "content": f"Gagal menghubungi server: {e}"})
        st.rerun()

with tab_dompet:
    st.markdown('<p style="color:#f9a8d4; font-weight:bold; font-size:20px;">RDN & PORTOFOLIO INVESTASI</p>', unsafe_allow_html=True)

    username_db = st.session_state.get('username', 'Guest')
    tot_dep, sisa = ambil_dompet(username_db)

    col_s1, col_s2 = st.columns(2)
    col_s1.metric("TOTAL DEPOSIT (MODAL SETOR)", f"Rp {tot_dep:,.0f}")
    col_s2.metric("CASH IN HAND (SALDO SIAP BELI)", f"Rp {sisa:,.0f}")
    st.divider()

    col_dep, col_beli, col_jual = st.columns(3)

    with col_dep:
        st.markdown('<p style="color:#86efac; font-weight:bold;">TOP UP DEPOSIT</p>', unsafe_allow_html=True)
        with st.form("form_deposit"):
            nominal = st.number_input("Nominal (Rp)", min_value=0, step=100000)
            if st.form_submit_button("Setor"):
                if nominal > 0:
                    setor_deposit(username_db, nominal)
                    st.success(f"Masuk Rp {nominal:,.0f}!")
                    st.rerun()

    with col_beli:
        st.markdown('<p style="color:#fcd34d; font-weight:bold;">BELI SAHAM</p>', unsafe_allow_html=True)
        with st.form("form_beli"):
            ticker_beli = st.text_input("Ticker Beli", "BBRI.JK").upper()
            lot_beli = st.number_input("Lot Beli", min_value=1, step=1)
            if st.form_submit_button("Beli"):
                try:
                    df_cek = yf.Ticker(ticker_beli).history(period="5d")
                    if not df_cek.empty:
                        harga_skrg = df_cek['Close'].iloc[-1]
                        ok, pesan_error = beli_saham(username_db, ticker_beli, lot_beli, harga_skrg)
                        if ok:
                            st.success(f"Beli {lot_beli} Lot sukses di harga Rp {harga_skrg:,.0f}!")
                            st.rerun()
                        else:
                            st.error(pesan_error)
                    else: st.error("Gagal menarik harga dari bursa.")
                except Exception as e: st.error(f"Gagal. Pastikan ticker benar (ex: BBRI.JK). Info: {e}")

    with col_jual:
        st.markdown('<p style="color:#fca5a5; font-weight:bold;">JUAL SAHAM</p>', unsafe_allow_html=True)
        with st.form("form_jual"):
            ticker_jual = st.text_input("Ticker Jual", "BBRI.JK").upper()
            lot_jual = st.number_input("Lot Jual", min_value=1, step=1)
            if st.form_submit_button("Jual"):
                try:
                    df_cek_jual = yf.Ticker(ticker_jual).history(period="5d")
                    if not df_cek_jual.empty:
                        harga_skrg = df_cek_jual['Close'].iloc[-1]
                        ok, pesan_error = eksekusi_jual(username_db, ticker_jual, lot_jual, harga_skrg)
                        if ok:
                            uang_masuk = harga_skrg * lot_jual * 100
                            st.success(f"Terjual! Saldo bertambah Rp {uang_masuk:,.0f} (Harga Rp {harga_skrg:,.0f}).")
                            st.rerun()
                        else:
                            st.error(pesan_error)
                    else: st.error("Gagal menarik harga terbaru.")
                except Exception as e: st.error(f"Gagal menghubungi pasar. Info: {e}")

    st.divider()

    st.markdown('<p style="color:#c084fc; font-weight:bold;">STATUS PORTOFOLIO & ESTIMASI DIVIDEN</p>', unsafe_allow_html=True)
    st.caption(f"Harga & nilai aset di bawah ini diambil langsung dari yfinance, terakhir disegarkan: {waktu_sekarang}")
    porto_db = ambil_portofolio(username_db)

    if porto_db:
        data_tabel = []
        for baris in porto_db:
            t_ticker = baris["ticker"]
            t_lot = baris["total_lot"]
            t_avg = baris["avg_weighted"] 
            h_skrg = ambil_harga_terkini(t_ticker, t_avg)

            try:
                d_rate = yf.Ticker(t_ticker).info.get('dividendRate', 0) or 0
            except Exception:
                d_rate = 0

            nilai_skrg = h_skrg * t_lot * 100
            modal = t_avg * t_lot * 100
            floating = nilai_skrg - modal
            est_div = d_rate * t_lot * 100

            data_tabel.append({
                "TICKER": t_ticker, "LOT": t_lot, "AVG PRICE": f"Rp {t_avg:,.0f}",
                "CURRENT PRICE": f"Rp {h_skrg:,.0f}", "P/L (Rp)": floating,
                "NILAI ASET": f"Rp {nilai_skrg:,.0f}", "EST. DIVIDEN/THN": f"Rp {est_div:,.0f}"
            })

        if data_tabel:
            df_porto = pd.DataFrame(data_tabel)
            st.dataframe(
                df_porto.style
                .format({"P/L (Rp)": "Rp {:,.0f}"})
                .map(lambda x: 'color: #86efac;' if x > 0 else ('color: #fca5a5;' if x < 0 else 'color: #e5e7eb;'), subset=['P/L (Rp)']),
                use_container_width=True, hide_index=True
            )
    else:
        st.info("Portofolio masih kosong. Silakan setor dana dan mulai berinvestasi!")

# ==========================================
# 8. FOOTER
# ==========================================
try: tahun_sekarang = datetime.now(zona_wib).year
except NameError: tahun_sekarang = datetime.now().year

st.markdown(f"""
<style>
.footer-wrapper {{ margin-top: 80px; padding-top: 40px; padding-bottom: 20px; border-top: 1px solid rgba(244, 114, 182, 0.2); background-color: transparent; position: relative; z-index: 2; }}
.footer-grid {{ display: grid; grid-template-columns: 2fr repeat(3, 1fr); gap: 30px; max-width: 1200px; margin: 0 auto; padding: 0 20px; }}
.footer-col h4 {{ color: #f9a8d4; font-size: 14px; font-weight: 700; margin-top: 0; margin-bottom: 16px; text-transform: uppercase; letter-spacing: 1px; }}
.footer-col p {{ color: #e9d5ff; font-size: 13px; line-height: 1.6; margin: 0; opacity: 0.8; }}
.footer-links {{ list-style: none; padding: 0; margin: 0; }}
.footer-links li {{ margin-bottom: 10px; font-size: 13px; color: #e9d5ff; opacity: 0.8; transition: all 0.2s ease; cursor: pointer; display: flex; align-items: center; }}
.footer-links li:hover {{ color: #c084fc; opacity: 1; transform: translateX(5px); }}
.footer-bottom {{ text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid rgba(244, 114, 182, 0.1); font-size: 12px; color: rgba(233, 213, 255, 0.6); letter-spacing: 1px; }}

@media (max-width: 768px) {{
    .footer-grid {{ grid-template-columns: 1fr; text-align: left; gap: 35px; padding: 0 15px; }}
    .footer-col h4 {{ text-align: left; border-bottom: 1px solid rgba(244, 114, 182, 0.3); padding-bottom: 8px; margin-bottom: 12px; display: inline-block; width: auto; }}
    .footer-col p {{ text-align: justify; }}
    .footer-links li {{ text-align: left; justify-content: flex-start; margin-bottom: 12px; font-size: 14px; }}
}}
</style>

<div class="footer-wrapper">
    <div class="footer-grid">
        <div class="footer-col">
            <h4>Terminal Saham</h4>
            <p>Platform komputasi independen yang bergerak di bidang analisis kuantitatif, pemodelan data pasar modal, dan otomasi berbasis AI untuk Bursa Efek Indonesia.</p>
        </div>
        <div class="footer-col">
            <h4>Navigasi</h4>
            <ul class="footer-links">
                <li>Arsitektur Beranda</li>
                <li>Pusat Dasbor</li>
                <li>Simulasi Portofolio</li>
                <li>Integrasi Transmisi</li>
            </ul>
        </div>
        <div class="footer-col">
            <h4>Legalitas</h4>
            <ul class="footer-links">
                <li>Ketentuan Layanan</li>
                <li>Kebijakan Privasi</li>
                <li>Keamanan Data</li>
                <li>Protokol Sistem</li>
            </ul>
        </div>
        <div class="footer-col">
            <h4>Spesifikasi</h4>
            <ul class="footer-links">
                <li>Database: SQLite3</li>
                <li>Mesin AI: Llama-3.3-70B</li>
                <li>API: Telegram Bot</li>
                <li>Data Feed: YFinance</li>
            </ul>
        </div>
    </div>
    <div class="footer-bottom">
        &copy; {tahun_sekarang} Terminal Saham Protokol v.4. Seluruh hak cipta dilindungi.
    </div>
</div>
""", unsafe_allow_html=True)