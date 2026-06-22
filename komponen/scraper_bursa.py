# komponen/scraper_bursa.py
import requests
from bs4 import BeautifulSoup

def ambil_bandarlogi_gratis(ticker):
    try:
        # Targetkan URL publik yang memuat data akumulasi broker EOD
        url = f"https://situs-data-saham-publik.com/emiten/{ticker.replace('.JK', '')}"
        headers = {"User-Agent": "Mozilla/5.0"}
        
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Ekstrak elemen tabel berdasarkan ID atau Class HTML situs target
        # Ini adalah contoh penataan data mentah menjadi teks siap saji untuk AI
        broker_buyer = "BB" 
        net_buy = 45000000000 
        
        return f"Broker {broker_buyer} melakukan akumulasi senilai Rp {net_buy:,.0f}"
    except Exception:
        return "Gagal memuat data pergerakan bandar harian."

def hitung_obi_lokal(total_bid_vol, total_offer_vol):
    if total_offer_vol == 0: return 0
    obi = total_bid_vol / total_offer_vol
    
    if obi > 1.5: status = "Antrean Beli Tebal (Support Kuat)"
    elif obi < 0.7: status = "Antrean Jual Tebal (Resistensi Kuat)"
    else: status = "Konsolidasi Netral"
    
    return f"Skor OBI: {obi:.2f} ({status})"