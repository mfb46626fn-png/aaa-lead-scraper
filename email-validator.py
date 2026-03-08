import json
import re
import smtplib
import dns.resolver

class EmailValidator:
    def __init__(self):
        self.tr_to_en = {
            'ç': 'c', 'ğ': 'g', 'ı': 'i', 'i': 'i', 'ö': 'o', 'ş': 's', 'ü': 'u',
            'Ç': 'c', 'Ğ': 'g', 'I': 'i', 'İ': 'i', 'Ö': 'o', 'Ş': 's', 'Ü': 'u'
        }

    def clean_text(self, text):
        if not text:
            return ""
        for tr_char, en_char in self.tr_to_en.items():
            text = text.replace(tr_char, en_char)
        text = re.sub(r'[^a-zA-Z0-9\s]', '', text).lower().strip()
        return text

    def generate_permutations(self, first_name, last_name, domain):
        """Önceki adımda yazdığımız tüm ihtimalleri üreten motor (Kısaltıldı)"""
        domain = domain.replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0]
        f_name_raw = self.clean_text(first_name)
        l_name_raw = self.clean_text(last_name)
        
        if not f_name_raw or not domain: return []

        f_name_joined = f_name_raw.replace(' ', '')
        l_name_joined = l_name_raw.replace(' ', '')
        f_parts = f_name_raw.split()
        l_parts = l_name_raw.split()
        f_first = f_parts[0] if f_parts else ""
        l_last = l_parts[-1] if l_parts else ""
        f_initial = f_first[0] if f_first else ""
        f_initials_all = "".join([p[0] for p in f_parts])
        l_initial = l_last[0] if l_last else ""

        permutations = set()

        if not l_last:
            permutations.add(f"{f_name_joined}@{domain}")
            permutations.add(f"{f_first}@{domain}")
            return list(permutations)

        patterns = [
            f"{f_first}@{domain}", f"{f_name_joined}@{domain}", f"{l_last}@{domain}", 
            f"{l_name_joined}@{domain}", f"{f_name_joined}.{l_name_joined}@{domain}", 
            f"{f_first}.{l_last}@{domain}", f"{f_name_joined}{l_name_joined}@{domain}", 
            f"{f_first}{l_last}@{domain}", f"{f_first}_{l_last}@{domain}", 
            f"{f_name_joined}_{l_name_joined}@{domain}", f"{f_first}-{l_last}@{domain}",
            f"{f_initial}{l_last}@{domain}", f"{f_initials_all}{l_last}@{domain}", 
            f"{f_initial}.{l_last}@{domain}", f"{f_initials_all}.{l_last}@{domain}", 
            f"{f_initial}_{l_last}@{domain}", f"{f_first}{l_initial}@{domain}", 
            f"{f_first}.{l_initial}@{domain}", f"{f_initial}{l_initial}@{domain}",
            f"{l_last}.{f_first}@{domain}", f"{l_last}{f_first}@{domain}", f"{l_last}_{f_first}@{domain}"
        ]

        if len(f_parts) > 1:
            f_second = f_parts[1]
            patterns.extend([
                f"{f_second}@{domain}", f"{f_second}.{l_last}@{domain}", 
                f"{f_second}{l_last}@{domain}", f"{f_second}_{l_last}@{domain}", 
                f"{f_first}.{f_second}.{l_last}@{domain}"
            ])

        for p in patterns:
            if p.count('@') == 1 and not p.startswith('.') and not p.startswith('_') and not p.startswith('-'):
                permutations.add(p)

        return sorted(list(permutations))

    def get_mx_record(self, domain):
        """Domain'in posta sunucusunu (MX Kaydı) bulur."""
        try:
            records = dns.resolver.resolve(domain, 'MX')
            # Google sunucularında bazen birden fazla kayıt olur, en önceliklisini (en düşük numara) al
            mx_record = sorted(records, key=lambda rec: rec.preference)[0].exchange.to_text()
            return mx_record
        except Exception as e:
            return None

    def verify_email_smtp(self, email, mx_record):
        """SMTP Ping atarak mail adresinin varlığını kontrol eder (Google Bypass Taktikli)."""
        # Hata yakalamak için dışarıya ne döndüğünü görmek istiyoruz
        try:
            # 1. Sunucuya bağlan (Port 25). ISP engellerse direkt hata verir.
            server = smtplib.SMTP(timeout=10)
            server.connect(mx_record, 25)
            
            # 2. Kendimizi "Bilinmeyen bir sunucu" gibi tanıtıyoruz (Google'ı şaşırtmak için)
            server.helo('mail.example.com')
            
            # 3. İŞTE HACK BURADA: Göndericiyi "Boş" (<>) bırakıyoruz. 
            # Bu, "Ben sana bir hata raporu (Bounce) getiriyorum" demektir. Google bunu reddedemez.
            server.mail('')
            
            # 4. Asıl soru: "Bu mail adresi var mı?"
            code, message = server.rcpt(str(email))
            
            server.quit()
            
            # 250 kodu başarılı (Bu mail var) demektir.
            if code == 250:
                return True
            else:
                # Ekranda Google'ın neden reddettiğini (550 vb.) görelim
                print(f" [HATA KODU: {code}] ", end="")
                return False
                
        except TimeoutError:
            print(" [TIMEOUT: İnternet Sağlayıcın Port 25'i Engelliyor!] ", end="")
            return False
        except Exception as e:
            print(f" [SİSTEM HATASI: {str(e)[:30]}] ", end="")
            return False

    def find_valid_email(self, first_name, last_name, domain):
        """Tüm süreci yönetir ve ilk bulduğu gerçek maili döndürür."""
        print(f"\n[*] Hedef: {first_name} {last_name} | Domain: {domain}")
        
        emails = self.generate_permutations(first_name, last_name, domain)
        print(f"[*] Üretilen İhtimal Sayısı: {len(emails)}")

        mx_record = self.get_mx_record(domain)
        if not mx_record:
            return {"status": "failed", "reason": "Firmanın mail sunucusu (MX) bulunamadı."}

        print(f"[*] Hedef Posta Sunucusu (MX): {mx_record}")
        print("[*] Doğrulama Başladı (Sırayla kapılar çalınıyor)...\n")

        valid_email = None

        for email in emails:
            print(f"  -> Deneniyor: {email} ... ", end="", flush=True)
            
            if self.verify_email_smtp(email, mx_record):
                print("✅ BULUNDU!")
                valid_email = email
                break # Doğruyu bulduğumuz an diğerlerini denemeyi bırakıyoruz!
            else:
                print("❌")

        if valid_email:
            return {
                "status": "success",
                "isim": f"{first_name} {last_name}",
                "domain": domain,
                "bulunan_mail": valid_email
            }
        else:
            return {
                "status": "failed",
                "reason": "Hiçbir ihtimal doğrulanamadı (Manuel operasyona aktarılmalı)."
            }

if __name__ == "__main__":
    validator = EmailValidator()
    
    # Sistemin kendi üzerinde test edelim
    isim = "Murat Can"
    soyisim = "info"
    hedef_domain = "wecahan.com"
    
    sonuc = validator.find_valid_email(isim, soyisim, hedef_domain)
    
    print("\n--- VALİDATÖR FİNAL ÇIKTISI ---")
    print(json.dumps(sonuc, indent=4, ensure_ascii=False))