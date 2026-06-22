import os
from komponen.pdf_parser import ambil_metrik_pdf

print("=== MEMULAI INVESTIGASI PDF ===")
jalur = "data_laporan/laporan_bbri.pdf"

if os.path.exists(jalur):
    print("[+] File PDF ditemukan di sistem!")
    print("[+] Sedang mencoba membaca isi PDF menggunakan pdf_parser.py...")
    try:
        hasil = ambil_metrik_pdf(jalur)
        print("\n=== HASIL BACAAN MESIN ===")
        print(hasil)
        print("==========================")
    except Exception as e:
        print(f"\n[!] TERJADI ERROR SAAT MEMBACA: {e}")
else:
    print("[!] GAGAL: File PDF tidak ditemukan di jalur:", jalur)