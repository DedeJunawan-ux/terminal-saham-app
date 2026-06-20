import streamlit as st

# 1. Konfigurasi Halaman Utama
st.set_page_config(page_title="Terminal Saham", layout="wide", initial_sidebar_state="expanded")

# 2. Inisialisasi Sesi Login
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = ''

# 3. Deklarasi File Halaman
halaman_gateway = st.Page("halaman/landing.py", title="Gateway & Login")
halaman_utama = st.Page("halaman/dashboard.py", title="Dashboard Utama")

# 4. Logika Navigasi Dinamis
if not st.session_state['logged_in']:
    # Jika belum login, paksa ke halaman Landing
    pg = st.navigation([halaman_gateway])
else:
    # Jika sudah login, buka halaman Dashboard
    pg = st.navigation([halaman_utama])

pg.run()