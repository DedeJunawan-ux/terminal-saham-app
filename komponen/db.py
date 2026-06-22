"""
komponen/db.py
================
Modul terpusat untuk SEMUA operasi database SQLite.

Tujuan modul ini:
- landing.py dan dashboard.py tidak lagi punya logic SQL masing-masing
  (sebelumnya init_db() dan koneksi sqlite3 ditulis ulang di dua tempat).
- Operasi yang menyentuh uang (beli/jual/deposit) dibungkus jadi SATU
  transaksi atomik per fungsi, supaya tidak ada celah "baca saldo di Python,
  baru tulis balik" yang rawan race condition kalau user buka beberapa tab.
- Query rata-rata harga beli portofolio diperbaiki jadi rata-rata
  TERTIMBANG berdasarkan lot, bukan rata-rata sederhana antar baris.
"""

import sqlite3
import hashlib
from contextlib import contextmanager

DB_PATH = "terminal_saham.db"


@contextmanager
def get_conn():
    """
    Context manager: connection selalu ditutup, dan otomatis commit kalau
    sukses / rollback kalau ada exception. Jadi tiap fungsi di bawah cukup
    'with get_conn() as conn:' tanpa perlu conn.commit()/conn.close() manual.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """Buat semua tabel kalau belum ada. Aman dipanggil berkali-kali."""
    with get_conn() as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS riwayat_laporan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            waktu TEXT,
            laporan TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT,
            nama_bank TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS dompet (
            username TEXT PRIMARY KEY,
            total_deposit REAL,
            sisa_saldo REAL
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS kepemilikan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            ticker TEXT,
            lot INTEGER,
            harga_avg REAL
        )''')
        # Tabel kecil untuk status global lintas-sesi, dipakai supaya
        # laporan AI otomatis tidak terkirim berkali-kali kalau ada
        # beberapa user yang membuka dashboard bersamaan.
        c.execute('''CREATE TABLE IF NOT EXISTS status_sistem (
            kunci TEXT PRIMARY KEY,
            nilai TEXT
        )''')


# ==========================================
# AUTENTIKASI
# ==========================================

def hash_password(password):
    return hashlib.sha256(str.encode(password)).hexdigest()


def cek_login(username, password):
    """True kalau kombinasi username+password cocok."""
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT 1 FROM users WHERE username=? AND password=?",
            (username, hash_password(password))
        )
        return c.fetchone() is not None


def daftar_user(username, password, nama_bank):
    """
    Return (True, None) kalau sukses.
    Return (False, pesan_error) kalau username sudah dipakai / input kosong.
    """
    if not username or not password:
        return False, "Username dan password wajib diisi."
    with get_conn() as conn:
        c = conn.cursor()
        try:
            c.execute(
                "INSERT INTO users (username, password, nama_bank) VALUES (?, ?, ?)",
                (username, hash_password(password), nama_bank)
            )
            c.execute(
                "INSERT INTO dompet (username, total_deposit, sisa_saldo) VALUES (?, 0, 0)",
                (username,)
            )
            return True, None
        except sqlite3.IntegrityError:
            return False, "Nama pengguna tersebut telah terdaftar."


# ==========================================
# LAPORAN AI
# ==========================================

def simpan_ke_db(waktu, laporan):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO riwayat_laporan (waktu, laporan) VALUES (?, ?)",
            (waktu, laporan)
        )


def ambil_riwayat_laporan(limit=50, filter_like=None):
    """
    Ambil baris riwayat_laporan terbaru, opsional difilter dengan SQL LIKE
    di kolom `waktu` (mis. filter_like="[CANDLESTICK-BBRI.JK]%" untuk cuma
    ambil riwayat candlestick ticker tertentu).

    Pendekatan filter lewat kolom `waktu` dipakai supaya TIDAK perlu migrasi
    skema (tambah kolom `kategori`/`ticker` baru) -- label kategori dititipkan
    sebagai prefix teks di kolom waktu saat disimpan (lihat app.py, fungsi
    Pindai Candlestick). Kalau ke depannya kategori makin banyak/kompleks,
    pertimbangkan migrasi ke kolom terpisah supaya query tidak bergantung ke
    format string.
    """
    with get_conn() as conn:
        c = conn.cursor()
        if filter_like:
            c.execute(
                "SELECT id, waktu, laporan FROM riwayat_laporan "
                "WHERE waktu LIKE ? ORDER BY id DESC LIMIT ?",
                (filter_like, limit)
            )
        else:
            c.execute(
                "SELECT id, waktu, laporan FROM riwayat_laporan ORDER BY id DESC LIMIT ?",
                (limit,)
            )
        return [dict(row) for row in c.fetchall()]


# ==========================================
# STATUS SISTEM (lock global, bukan session_state)
# ==========================================

def ambil_status(kunci, default=""):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT nilai FROM status_sistem WHERE kunci=?", (kunci,))
        row = c.fetchone()
        return row["nilai"] if row else default


def set_status(kunci, nilai):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO status_sistem (kunci, nilai) VALUES (?, ?) "
            "ON CONFLICT(kunci) DO UPDATE SET nilai=excluded.nilai",
            (kunci, nilai)
        )


# ==========================================
# DOMPET
# ==========================================

def ambil_dompet(username):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT total_deposit, sisa_saldo FROM dompet WHERE username=?", (username,))
        row = c.fetchone()
        return (row["total_deposit"], row["sisa_saldo"]) if row else (0.0, 0.0)


def setor_deposit(username, nominal):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "UPDATE dompet SET total_deposit = total_deposit + ?, "
            "sisa_saldo = sisa_saldo + ? WHERE username=?",
            (nominal, nominal, username)
        )


def beli_saham(username, ticker, lot, harga):
    """
    Beli saham: kurangi saldo & catat kepemilikan dalam SATU transaksi.

    Pengecekan saldo dilakukan lewat klausa WHERE pada UPDATE itu sendiri
    (sisa_saldo >= total_biaya), bukan baca-dulu-baru-tulis di Python.
    Ini membuat cek-dan-kurangi saldo atomik di level database, sehingga
    tidak ada celah race condition meski ada beberapa transaksi nyaris
    bersamaan dari sesi yang sama.

    Return (True, None) kalau sukses, (False, pesan_error) kalau saldo kurang.
    """
    total_biaya = harga * lot * 100
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "UPDATE dompet SET sisa_saldo = sisa_saldo - ? "
            "WHERE username=? AND sisa_saldo >= ?",
            (total_biaya, username, total_biaya)
        )
        if c.rowcount == 0:
            return False, f"Saldo RDN kurang! Butuh Rp {total_biaya:,.0f}"
        c.execute(
            "INSERT INTO kepemilikan (username, ticker, lot, harga_avg) VALUES (?, ?, ?, ?)",
            (username, ticker, lot, harga)
        )
        return True, None


def eksekusi_jual(username, ticker, lot_jual, harga_jual):
    """
    Jual saham dengan matching FIFO (lot tertua dijual duluan), lalu saldo
    dikredit. Semua ini satu transaksi: kalau ada error di tengah jalan,
    seluruh perubahan di-rollback otomatis oleh get_conn().

    Return (True, None) kalau sukses, (False, pesan_error) kalau lot
    yang dimiliki kurang dari lot yang mau dijual.
    """
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "SELECT COALESCE(SUM(lot), 0) AS total FROM kepemilikan WHERE username=? AND ticker=?",
            (username, ticker)
        )
        total_owned = c.fetchone()["total"]
        if total_owned < lot_jual:
            return False, f"Gagal. Kamu hanya punya {total_owned} Lot."

        uang_masuk = harga_jual * lot_jual * 100
        c.execute(
            "UPDATE dompet SET sisa_saldo = sisa_saldo + ? WHERE username=?",
            (uang_masuk, username)
        )

        sisa_jual = lot_jual
        c.execute(
            "SELECT id, lot FROM kepemilikan WHERE username=? AND ticker=? ORDER BY id ASC",
            (username, ticker)
        )
        for row in c.fetchall():
            if sisa_jual == 0:
                break
            row_id, row_lot = row["id"], row["lot"]
            if row_lot <= sisa_jual:
                c.execute("DELETE FROM kepemilikan WHERE id=?", (row_id,))
                sisa_jual -= row_lot
            else:
                c.execute("UPDATE kepemilikan SET lot = lot - ? WHERE id=?", (sisa_jual, row_id))
                sisa_jual = 0
        return True, None


def ambil_portofolio(username):
    """
    List kepemilikan per ticker dengan harga rata-rata TERTIMBANG lot
    (SUM(lot*harga) / SUM(lot)) -- ini perbaikan dari versi lama yang
    pakai AVG(harga_avg) biasa dan hasilnya salah kalau jumlah lot per
    transaksi beli berbeda-beda.
    """
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            """SELECT ticker,
                      SUM(lot) AS total_lot,
                      SUM(lot * harga_avg) * 1.0 / SUM(lot) AS avg_weighted
               FROM kepemilikan
               WHERE username=?
               GROUP BY ticker""",
            (username,)
        )
        return [dict(row) for row in c.fetchall()]