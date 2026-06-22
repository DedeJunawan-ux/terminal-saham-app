import streamlit as st
from komponen.db import init_db

st.set_page_config(page_title="Terminal Saham", layout="wide", initial_sidebar_state="expanded")

# 2. Inisialisasi Database 
init_db()

# 3. Inisialisasi Sesi Login
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False
if 'username' not in st.session_state:
    st.session_state['username'] = ''

# 4. Deklarasi File Halaman
halaman_gateway = st.Page("halaman/landing.py", title="Gateway & Login")
halaman_utama = st.Page("halaman/dashboard.py", title="Dashboard Utama")

# 5. Logika Navigasi Dinamis
if not st.session_state['logged_in']:
    # Jika belum login, paksa ke halaman Landing
    pg = st.navigation([halaman_gateway])
else:
    # Jika sudah login, buka halaman Dashboard
    pg = st.navigation([halaman_utama])

pg.run()