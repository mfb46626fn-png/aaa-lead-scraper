import json
from ddgs import DDGS

class DDGScraper:
    def __init__(self):
        # Aradığımız kilit unvanlar
        self.target_titles = [
            "CEO", "Owner", "Founder", "Co-Founder", 
            "Marketing Director", "Manager"
        ]
        self.max_profiles = 10

    def create_search_query(self, company_name):
        """Arama motoruna atılacak o özel metni (Dork) hazırlar."""
        titles = " OR ".join(f'"{t}"' for t in self.target_titles)
        query = f'site:linkedin.com/in "{company_name}" ({titles})'
        return query

    def parse_profile(self, title_text, url):
        """Karmaşık DDG başlıklarını temizler ve Ad, Soyad, Unvan ayırır."""
        # Örnek: "Demet Suzan Mutlu - Trendyol Group | LinkedIn Atacan..."
        # Önce "|" işaretiyle bölüp sadece en soldaki asıl kişiyi alalım
        clean_title = title_text.split("|")[0].strip()
        
        # Sonra " - " işaretiyle bölüp İsim ve Unvan/Şirket kısımlarını ayıralım
        parts = clean_title.split(" - ")
        
        name_part = parts[0].strip()
        # Ad ve Soyadı ayır
        name_words = name_part.split()
        if len(name_words) >= 2:
            first_name = " ".join(name_words[:-1])
            last_name = name_words[-1]
        else:
            first_name = name_part
            last_name = ""

        # Eğer unvan kısmı varsa al, yoksa 'Yetkili' yaz
        title_part = parts[1].strip() if len(parts) > 1 else "Yetkili"
        
        return {
            "first_name": first_name,
            "last_name": last_name,
            "title": title_part,
            "source_url": url
        }

    def process(self, input_data):
        """n8n'den gelen veriyi karşılar ve işlemleri başlatır."""
        company_name = input_data.get("firma_adi")
        
        if not company_name:
            return {"status": "error", "message": "Firma adı bulunamadı."}

        query = self.create_search_query(company_name)
        profiles = []

        print(f"[*] '{company_name}' için Hayalet Motor (DDGS) çalıştırılıyor...")
        
        try:
            with DDGS() as ddgs:
                # Arama yap ve limitimiz kadar sonucu getir
                results = list(ddgs.text(query, max_results=self.max_profiles))
                
                for res in results:
                    url = res.get('href')
                    title_text = res.get('title')
                    
                    # Sadece geçerli LinkedIn kişi linklerini kabul et
                    if url and "linkedin.com/in/" in url:
                        profile_data = self.parse_profile(title_text, url)
                        profiles.append(profile_data)
                        
        except Exception as e:
            return {"status": "error", "message": f"Arama motoru hatası: {e}"}

        # Eğer hiç profil bulunamadıysa (Manuel'e düşmesi için)
        if not profiles:
            return {
                "status": "failed", 
                "hedef_firma": company_name,
                "message": "Firma yetkilisi bulunamadı."
            }

        # Başarılı sonuç dönüşü
        return {
            "status": "success",
            "hedef_firma": company_name,
            "toplam_bulunan": len(profiles),
            "data": profiles
        }

if __name__ == "__main__":
    # n8n'den gelecek örnek verinin simülasyonu
    test_data = {
        "firma_adi": "Trendyol",
        "web_sitesi": "trendyol.com"
    }
    
    bot = DDGScraper()
    result = bot.process(test_data)
    
    print("\n--- SCRAPER FİNAL ÇIKTISI (AAA FABRİKASI İÇİN HAZIR) ---")
    print(json.dumps(result, indent=4, ensure_ascii=False))