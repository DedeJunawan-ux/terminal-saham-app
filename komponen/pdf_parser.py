# komponen/pdf_parser.py
import pdfplumber

def ambil_metrik_pdf(jalur_file):
    """
    Membaca file PDF laporan keuangan dan mengekstrak teks mentahnya
    untuk dikirim ke AI sebagai konteks fundamental.
    """
    try:
        with pdfplumber.open(jalur_file) as pdf:
            teks = ""
            for halaman in pdf.pages[:5]:  # Ambil maks 5 halaman pertama
                teks += halaman.extract_text() or ""
        
        if not teks.strip():
            return "PDF ditemukan tapi tidak ada teks yang bisa diekstrak (mungkin file scan/gambar)."
        
        # Potong supaya tidak terlalu panjang dikirim ke AI
        return teks[:3000]
    
    except Exception as e:
        return f"Gagal membaca PDF: {e}"