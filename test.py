from ddgs import DDGS

# Test için dev bir firma deneyelim ki sorunun DDG indexinden mi kaynaklandığını görelim.
query = 'site:linkedin.com/in "Trendyol" ("CEO" OR "Founder" OR "Manager" OR "Director")'

print("[*] DDGS Motoru (Yeni Sürüm) Başlatılıyor...")

try:
    with DDGS() as ddgs:
        # Arama yap ve ilk 10 sonucu getir
        results = list(ddgs.text(query, max_results=10))
        
        print(f"[*] İşlem Başarılı! Bulunan sonuç sayısı: {len(results)}\n")
        
        if results:
            print("[+] BULUNAN PROFİLLER (TRENDYOL):")
            for res in results:
                print(f"- Başlık: {res.get('title')}")
                print(f"  Link: {res.get('href')}\n")
        else:
            print("[-] Hala 0 sonuç. DDG bu Dork yapısını API'de engelliyor olabilir.")
            
except Exception as e:
    print(f"[!] Bir hata oluştu: {e}")