import streamlit as st
from datetime import datetime
import pytz
from komponen.db import cek_login, daftar_user

zona_wib = pytz.timezone('Asia/Jakarta')

# CATATAN: init_db() TIDAK dipanggil di sini lagi.
# Sekarang dipanggil sekali saja dari app.py sebelum navigasi dijalankan,
# supaya landing.py dan dashboard.py tidak masing-masing punya salinan
# logic inisialisasi database sendiri.

# ==========================================
# CSS: SOLID DARK MODE + ANIMATED BACKGROUND & SAKURA
# ==========================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    /* ─── PENGHILANG MENU BAWAAN STREAMLIT ─── */
    header { background: transparent !important; }
    [data-testid="stHeader"] { background: transparent !important; }
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    .block-container { padding-top: 2rem !important; max-width: 1100px !important; }

    /* PEMBASMI TOMBOL FORK & GITHUB CLOUD */
    [data-testid="stToolbar"] { display: none !important; }
    .viewerBadge_container { display: none !important; }
    .viewerBadge_link { display: none !important; }

    /* ─── BACKGROUND BERANIMASI (HIDUP TAPI ELEGAN) ─── */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
        background: linear-gradient(160deg, #0f172a 0%, #020617 100%) !important;
        color: #f8fafc !important;
        font-family: 'Inter', sans-serif !important;
    }

    /* ─── KUMPULAN ANIMASI ─── */
    @keyframes fadeInUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
    @keyframes gradientShift { 0% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } 100% { background-position: 0% 50%; } }
    @keyframes orbFloat { 0% { transform: translate(0, 0) scale(1); } 50% { transform: translate(30px, -20px) scale(1.1); } 100% { transform: translate(0, 0) scale(1); } }

    /* Animasi Sakura */
    @keyframes sakuraFall { 0% { transform: translate(0, -20px) rotate(0deg); opacity: 0; } 10% { opacity: 0.6; } 90% { opacity: 0.4; } 100% { transform: translate(40px, 110vh) rotate(720deg); opacity: 0; } }
    @keyframes sakuraFall2 { 0% { transform: translate(0, -20px) rotate(0deg); opacity: 0; } 10% { opacity: 0.5; } 100% { transform: translate(-30px, 110vh) rotate(-540deg); opacity: 0; } }

    /* ─── CAHAYA LATAR BELAKANG (ORBS) ─── */
    .stApp::before {
        content: ''; position: fixed; top: 0; left: 0; right: 0; bottom: 0;
        background: radial-gradient(ellipse at 15% 20%, rgba(99, 102, 241, 0.08) 0%, transparent 45%),
                    radial-gradient(ellipse at 85% 80%, rgba(168, 85, 247, 0.08) 0%, transparent 45%);
        pointer-events: none; z-index: 0;
        animation: orbFloat 15s ease-in-out infinite;
    }

    /* ─── SAKURA PETALS ─── */
    .sakura-wrap { position: fixed; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; z-index: 1; overflow: hidden; }
    .petal { position: absolute; top: -30px; font-size: 15px; opacity: 0; animation: sakuraFall linear infinite; filter: drop-shadow(0 0 3px rgba(244, 114, 182, 0.4)); }
    .petal:nth-child(1)  { left: 10%; animation-duration: 11s; animation-delay: 0s; }
    .petal:nth-child(2)  { left: 35%; animation-duration: 14s; animation-delay: 3s; font-size: 12px; animation-name: sakuraFall2; }
    .petal:nth-child(3)  { left: 60%; animation-duration: 9s;  animation-delay: 5s; font-size: 18px; }
    .petal:nth-child(4)  { left: 85%; animation-duration: 13s; animation-delay: 1s; font-size: 14px; animation-name: sakuraFall2; }

    /* ─── HERO HEADER ─── */
    .gateway-header { text-align: center; margin-bottom: 3rem; animation: fadeInUp 0.8s ease-out forwards; position: relative; z-index: 2; }
    .gateway-title {
        font-size: 3.8rem; font-weight: 800; letter-spacing: -1px; margin-bottom: 0.5rem;
        background: linear-gradient(270deg, #38bdf8, #818cf8, #c084fc, #38bdf8);
        background-size: 300% 300%;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        animation: gradientShift 6s ease infinite;
    }
    .gateway-subtitle { font-size: 1.1rem; color: #94a3b8; font-weight: 500; letter-spacing: 1px; }

    /* ─── KONTEN PANEL KIRI ─── */
    .info-container {
        background-color: #1e293b; padding: 40px; border-radius: 16px; border: 1px solid #334155;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
        animation: fadeInUp 0.8s ease-out forwards; animation-delay: 0.1s; opacity: 0;
        position: relative; z-index: 2;
    }
    .section-title { color: #f8fafc; font-size: 1.5rem; font-weight: 700; margin-top: 0; margin-bottom: 15px; }
    .section-desc { color: #cbd5e1; font-size: 15px; line-height: 1.6; margin-bottom: 30px; }

    .features-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 16px; }
    .feature-card {
        background-color: #0f172a; border: 1px solid #334155; padding: 20px; border-radius: 12px;
        transition: all 0.3s ease;
    }
    .feature-card:hover {
        border-color: #818cf8; transform: translateY(-5px);
        box-shadow: 0 10px 20px rgba(129, 140, 248, 0.15);
    }
    .feature-card h5 { color: #818cf8; font-size: 15px; font-weight: 600; margin: 0 0 8px 0; }
    .feature-card p { color: #94a3b8; font-size: 13px; line-height: 1.5; margin: 0; }

    /* ─── STYLING FORM LOGIN (PANEL KANAN) ─── */
    button[data-baseweb="tab"] { background-color: transparent !important; color: #94a3b8 !important; font-weight: 600 !important; }
    button[data-baseweb="tab"][aria-selected="true"] { color: #818cf8 !important; border-bottom-color: #818cf8 !important; }

    [data-testid="stForm"] {
        background-color: #1e293b !important;
        border-radius: 16px !important;
        border: 1px solid #334155 !important;
        padding: 30px !important;
        box-shadow: 0 15px 30px rgba(0, 0, 0, 0.4) !important;
        animation: fadeInUp 0.8s ease-out forwards; animation-delay: 0.2s; opacity: 0;
        position: relative; z-index: 2;
    }

    .stTextInput input, .stSelectbox div[data-baseweb="select"] > div {
        background-color: #0f172a !important; color: #f8fafc !important;
        border: 1px solid #475569 !important; border-radius: 8px !important; padding: 0.5rem !important; transition: border-color 0.3s;
    }
    .stTextInput input:focus { border-color: #818cf8 !important; box-shadow: 0 0 0 1px #818cf8 !important; }
    div[data-testid="stCheckbox"] label { color: #cbd5e1 !important; font-size: 14px !important; }

    .stButton > button {
        background: linear-gradient(135deg, #6366f1, #4f46e5) !important; color: #ffffff !important;
        border: none !important; border-radius: 8px !important; font-size: 14px !important;
        font-weight: 600 !important; padding: 10px 0 !important; transition: all 0.3s ease !important;
    }
    .stButton > button:hover { transform: scale(1.02); box-shadow: 0 5px 15px rgba(79, 70, 229, 0.4); color: white !important; }

    /* ─── FOOTER (tema sakura, konsisten dengan dashboard) ─── */
    .footer-wrapper { margin-top: 80px; padding-top: 40px; padding-bottom: 20px; border-top: 1px solid rgba(244, 114, 182, 0.2); background-color: transparent; position: relative; z-index: 2; }
    .footer-grid { display: grid; grid-template-columns: 2fr repeat(3, 1fr); gap: 30px; max-width: 1200px; margin: 0 auto; padding: 0 20px; }
    .footer-col h4 { color: #f9a8d4; font-size: 14px; font-weight: 700; margin-top: 0; margin-bottom: 16px; text-transform: uppercase; letter-spacing: 1px; }
    .footer-col p { color: #e9d5ff; font-size: 13px; line-height: 1.6; margin: 0; opacity: 0.8; }
    .footer-links { list-style: none; padding: 0; margin: 0; }
    .footer-links li { margin-bottom: 10px; font-size: 13px; color: #e9d5ff; opacity: 0.8; transition: all 0.2s ease; cursor: pointer; display: flex; align-items: center; }
    .footer-links li:hover { color: #c084fc; opacity: 1; transform: translateX(5px); }
    .footer-bottom { text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid rgba(244, 114, 182, 0.1); font-size: 12px; color: rgba(233, 213, 255, 0.6); letter-spacing: 1px; }

    @media (max-width: 768px) {
        .footer-grid { grid-template-columns: 1fr; text-align: left; gap: 35px; padding: 0 15px; }
        .footer-col h4 { text-align: left; border-bottom: 1px solid rgba(244, 114, 182, 0.3); padding-bottom: 8px; margin-bottom: 12px; display: inline-block; width: auto; }
        .footer-col p { text-align: justify; }
        .footer-links li { text-align: left; justify-content: flex-start; margin-bottom: 12px; font-size: 14px; }
    }
</style>

<div class="sakura-wrap">
    <div class="petal">🌸</div><div class="petal">🌸</div><div class="petal">🌸</div><div class="petal">🌸</div>
</div>
""", unsafe_allow_html=True)

# ==========================================
# HERO HEADER
# ==========================================
st.markdown("""
<div class="gateway-header">
    <h1 class="gateway-title">Terminal Saham</h1>
    <div class="gateway-subtitle">Sistem Analisis Kuantitatif dan Otomasi Pasar Modal</div>
</div>
""", unsafe_allow_html=True)

col_info, col_space, col_form = st.columns([1.2, 0.1, 1])

with col_info:
    st.markdown("""
    <div class="info-container">
        <h3 class="section-title">Infrastruktur Analisis Terpadu</h3>
        <p class="section-desc">
            Terminal Saham memfasilitasi pemantauan pergerakan bursa Indonesia secara aktual. Kami menggabungkan filter fundamental mekanis dengan komputasi kecerdasan buatan untuk menghasilkan wawasan pasar yang objektif.
        </p>
        <div class="features-grid">
            <div class="feature-card">
                <h5>Nilai Intrinsik</h5>
                <p>Penyaringan mekanis otomatis untuk mendeteksi emiten berfundamental kuat di area harga diskon.</p>
            </div>
            <div class="feature-card">
                <h5>Komputasi AI</h5>
                <p>Pemrosesan data seketika yang merangkum sentimen makroekonomi menjadi laporan terstruktur.</p>
            </div>
            <div class="feature-card">
                <h5>Simulasi RDN</h5>
                <p>Pengujian strategi transaksi melalui rekening dana simulasi terintegrasi guna mengukur performa aset.</p>
            </div>
            <div class="feature-card" style="border-color: rgba(59, 130, 246, 0.4);">
                <h5 style="color: #60a5fa;">Integrasi Bot Telegram</h5>
                <p>Hubungkan akun dengan asisten virtual untuk menerima sinyal AI dan rangkuman pasar seketika di layar HP Anda.</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

with col_form:
    tab_login, tab_register = st.tabs(["LOGIN", "REGISTRASI AKUN"])

    with tab_login:
        with st.form("form_login_utama", clear_on_submit=False):
            st.markdown('<p style="color:#f8fafc; font-weight:600; font-size:16px; margin-bottom:5px;">Otentikasi Pengguna</p>', unsafe_allow_html=True)
            user_l = st.text_input("Nama Pengguna")
            pass_l = st.text_input("Kata Sandi", type="password")
            # CATATAN: checkbox ini sekarang hanya kosmetik / placeholder.
            # Streamlit session_state akan tetap reset begitu browser di-refresh
            # atau ditutup, jadi belum benar-benar membuat sesi "tetap masuk".
            # Untuk fitur remember-me yang sungguhan, perlu token persisten
            # (mis. cookie) -- belum diimplementasikan di versi ini.
            ingat_saya = st.checkbox(
                "Tetap masuk di perangkat ini (segera hadir)",
                value=True,
                disabled=True
            )

            st.markdown("<br>", unsafe_allow_html=True)
            submit_login = st.form_submit_button("Masuk", use_container_width=True)

            if submit_login:
                if cek_login(user_l, pass_l):
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = user_l
                    st.rerun()
                else:
                    st.error("Kredensial tidak valid. Silakan periksa kembali.")

    with tab_register:
        with st.form("form_registrasi_utama", clear_on_submit=True):
            st.markdown('<p style="color:#f8fafc; font-weight:600; font-size:16px; margin-bottom:5px;">Registrasi Personel Baru</p>', unsafe_allow_html=True)
            user_r = st.text_input("Nama Pengguna Baru")
            pass_r = st.text_input("Kata Sandi Baru", type="password")
            bank_r = st.selectbox("Afiliasi Perbankan RDN", ["BCA", "Mandiri", "BRI", "BNI", "Lainnya"])

            st.markdown("<br>", unsafe_allow_html=True)
            submit_register = st.form_submit_button("Daftarkan Akun", use_container_width=True)

            if submit_register:
                ok, pesan_error = daftar_user(user_r, pass_r, bank_r)
                if ok:
                    st.success("Registrasi berhasil. Silakan beralih ke tab Masuk Sistem.")
                else:
                    st.error(pesan_error)

# ==========================================
# FOOTER
# ==========================================
try:
    tahun_sekarang = datetime.now(zona_wib).year
except NameError:
    tahun_sekarang = datetime.now().year

st.markdown(f"""
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