"""
komponen/db.py  —  versi Supabase
==================================
Semua nama fungsi & parameter IDENTIK dengan versi SQLite sebelumnya,
sehingga dashboard.py, landing.py, dan app.py tidak perlu diubah sama sekali.

Perubahan arsitektur:
- sqlite3 / get_conn() dihapus, diganti supabase-py client
- get_supabase() di-cache dengan @st.cache_resource supaya koneksi
  tidak dibuat ulang tiap kali Streamlit me-rerun script
- Tabel dibuat lewat SQL Editor di dashboard Supabase (schema.sql),
  bukan dari kode Python -- init_db() sekarang jadi no-op
"""

import hashlib
import streamlit as st
from supabase import create_client, Client


@st.cache_resource
def get_supabase() -> Client:
    """
    Buat & cache Supabase client. Credentials diambil dari st.secrets
    (secrets.toml untuk lokal, Secrets di Streamlit Cloud untuk production).
    """
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_SECRET_KEY"]
    )


def init_db():
    """
    Di versi SQLite, fungsi ini membuat tabel kalau belum ada.
    Di versi Supabase, tabel sudah dibuat lewat schema.sql di SQL Editor,
    jadi fungsi ini sengaja dibiarkan kosong supaya pemanggilan
    init_db() di app.py / landing.py tidak error.
    """
    pass


# ==========================================
# AUTENTIKASI
# ==========================================

def hash_password(password: str) -> str:
    return hashlib.sha256(str.encode(password)).hexdigest()


def cek_login(username: str, password: str) -> bool:
    sb = get_supabase()
    result = (
        sb.table("users")
        .select("username")
        .eq("username", username)
        .eq("password", hash_password(password))
        .execute()
    )
    return len(result.data) > 0


def daftar_user(username: str, password: str, nama_bank: str):
    """
    Return (True, None) kalau sukses.
    Return (False, pesan_error) kalau username sudah dipakai / input kosong.
    """
    if not username or not password:
        return False, "Username dan password wajib diisi."
    sb = get_supabase()

    cek = sb.table("users").select("username").eq("username", username).execute()
    if cek.data:
        return False, "Nama pengguna tersebut telah terdaftar."

    try:
        sb.table("users").insert({
            "username": username,
            "password": hash_password(password),
            "nama_bank": nama_bank,
        }).execute()
        sb.table("dompet").insert({
            "username": username,
            "total_deposit": 0.0,
            "sisa_saldo": 0.0,
        }).execute()
        return True, None
    except Exception as e:
        return False, str(e)


# ==========================================
# LAPORAN AI
# ==========================================

def simpan_ke_db(waktu: str, laporan: str):
    sb = get_supabase()
    sb.table("riwayat_laporan").insert({"waktu": waktu, "laporan": laporan}).execute()


def ambil_riwayat_laporan(limit: int = 50, filter_like: str = None):
    """
    Ambil riwayat laporan terbaru. Opsional filter by prefix di kolom waktu
    (mis. filter_like="[CANDLESTICK-BBRI.JK]%").
    """
    sb = get_supabase()
    query = (
        sb.table("riwayat_laporan")
        .select("id, waktu, laporan")
        .order("id", desc=True)
        .limit(limit)
    )
    if filter_like:
        query = query.like("waktu", filter_like)
    return query.execute().data


# ==========================================
# STATUS SISTEM (lock global, bukan session_state)
# ==========================================

def ambil_status(kunci: str, default: str = "") -> str:
    sb = get_supabase()
    result = sb.table("status_sistem").select("nilai").eq("kunci", kunci).execute()
    return result.data[0]["nilai"] if result.data else default


def set_status(kunci: str, nilai: str):
    sb = get_supabase()
    sb.table("status_sistem").upsert({"kunci": kunci, "nilai": nilai}).execute()


# ==========================================
# DOMPET
# ==========================================

def ambil_dompet(username: str):
    sb = get_supabase()
    result = (
        sb.table("dompet")
        .select("total_deposit, sisa_saldo")
        .eq("username", username)
        .execute()
    )
    if result.data:
        return result.data[0]["total_deposit"], result.data[0]["sisa_saldo"]
    return 0.0, 0.0


def setor_deposit(username: str, nominal: float):
    sb = get_supabase()
    current = sb.table("dompet").select("total_deposit, sisa_saldo").eq("username", username).execute()
    if current.data:
        row = current.data[0]
        sb.table("dompet").update({
            "total_deposit": row["total_deposit"] + nominal,
            "sisa_saldo": row["sisa_saldo"] + nominal,
        }).eq("username", username).execute()


def beli_saham(username: str, ticker: str, lot: int, harga: float):
    """
    Beli saham: cek saldo, kurangi, lalu catat kepemilikan.
    Return (True, None) kalau sukses, (False, pesan_error) kalau saldo kurang.
    """
    total_biaya = harga * lot * 100
    sb = get_supabase()

    result = sb.table("dompet").select("sisa_saldo").eq("username", username).execute()
    if not result.data:
        return False, "Akun tidak ditemukan."

    sisa_saldo = result.data[0]["sisa_saldo"]
    if sisa_saldo < total_biaya:
        return False, f"Saldo RDN kurang! Butuh Rp {total_biaya:,.0f}"

    sb.table("dompet").update({
        "sisa_saldo": sisa_saldo - total_biaya
    }).eq("username", username).execute()

    sb.table("kepemilikan").insert({
        "username": username,
        "ticker": ticker,
        "lot": lot,
        "harga_avg": harga,
    }).execute()

    return True, None


def eksekusi_jual(username: str, ticker: str, lot_jual: int, harga_jual: float):
    """
    Jual saham dengan matching FIFO (lot tertua dijual duluan), lalu saldo
    dikredit.
    Return (True, None) kalau sukses, (False, pesan_error) kalau lot kurang.
    """
    sb = get_supabase()

    rows = (
        sb.table("kepemilikan")
        .select("id, lot")
        .eq("username", username)
        .eq("ticker", ticker)
        .order("id", desc=False)
        .execute()
        .data
    )

    total_owned = sum(r["lot"] for r in rows)
    if total_owned < lot_jual:
        return False, f"Gagal. Kamu hanya punya {total_owned} Lot."

    # Kredit saldo
    dompet = sb.table("dompet").select("sisa_saldo").eq("username", username).execute()
    sisa_saldo = dompet.data[0]["sisa_saldo"]
    uang_masuk = harga_jual * lot_jual * 100
    sb.table("dompet").update({
        "sisa_saldo": sisa_saldo + uang_masuk
    }).eq("username", username).execute()

    # FIFO: kurangi lot dari baris terlama
    sisa_jual = lot_jual
    for row in rows:
        if sisa_jual == 0:
            break
        row_id, row_lot = row["id"], row["lot"]
        if row_lot <= sisa_jual:
            sb.table("kepemilikan").delete().eq("id", row_id).execute()
            sisa_jual -= row_lot
        else:
            sb.table("kepemilikan").update({"lot": row_lot - sisa_jual}).eq("id", row_id).execute()
            sisa_jual = 0

    return True, None


def ambil_portofolio(username: str):
    """
    List kepemilikan per ticker dengan harga rata-rata TERTIMBANG lot
    -- identik dengan versi SQLite (SUM(lot*harga)/SUM(lot)).
    """
    sb = get_supabase()
    rows = (
        sb.table("kepemilikan")
        .select("ticker, lot, harga_avg")
        .eq("username", username)
        .execute()
        .data
    )

    if not rows:
        return []

    ticker_map = {}
    for row in rows:
        t = row["ticker"]
        if t not in ticker_map:
            ticker_map[t] = {"total_lot": 0, "total_nilai": 0.0}
        ticker_map[t]["total_lot"] += row["lot"]
        ticker_map[t]["total_nilai"] += row["lot"] * row["harga_avg"]

    return [
        {
            "ticker": t,
            "total_lot": v["total_lot"],
            "avg_weighted": v["total_nilai"] / v["total_lot"],
        }
        for t, v in ticker_map.items()
    ]