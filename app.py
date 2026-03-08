from flask import Flask, request, jsonify
import re
import smtplib
import dns.resolver
from ddgs import DDGS

app = Flask(__name__)

# --- 1. SCRAPER MOTORU ---
class DDGScraper:
    def __init__(self):
        self.target_titles = ["CEO", "Owner", "Founder", "Co-Founder", "Marketing Director", "Manager"]
        self.max_profiles = 5 # n8n zaman aşımına uğramasın diye ilk 5 yetkiliyi tarıyoruz

    def create_search_query(self, company_name):
        titles = " OR ".join(f'"{t}"' for t in self.target_titles)
        return f'site:linkedin.com/in "{company_name}" ({titles})'

    def parse_profile(self, title_text, url):
        clean_title = title_text.split("|")[0].strip()
        parts = clean_title.split(" - ")
        name_part = parts[0].strip()
        name_words = name_part.split()
        
        if len(name_words) >= 2:
            first_name = " ".join(name_words[:-1])
            last_name = name_words[-1]
        else:
            first_name = name_part
            last_name = ""

        title_part = parts[1].strip() if len(parts) > 1 else "Yetkili"
        return {"first_name": first_name, "last_name": last_name, "title": title_part, "source_url": url}

    def get_profiles(self, company_name):
        query = self.create_search_query(company_name)
        profiles = []
        try:
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=self.max_profiles))
                for res in results:
                    url = res.get('href')
                    if url and "linkedin.com/in/" in url:
                        profiles.append(self.parse_profile(res.get('title'), url))
        except Exception as e:
            print(f"[!] Scraper Hatası: {e}")
        return profiles

# --- 2. EMAIL VALIDATOR MOTORU ---
class EmailValidator:
    def __init__(self):
        self.tr_to_en = {'ç': 'c', 'ğ': 'g', 'ı': 'i', 'i': 'i', 'ö': 'o', 'ş': 's', 'ü': 'u',
                         'Ç': 'c', 'Ğ': 'g', 'I': 'i', 'İ': 'i', 'Ö': 'o', 'Ş': 's', 'Ü': 'u'}

    def clean_text(self, text):
        if not text: return ""
        for tr, en in self.tr_to_en.items(): text = text.replace(tr, en)
        return re.sub(r'[^a-zA-Z0-9\s]', '', text).lower().strip()

    def generate_permutations(self, first_name, last_name, domain):
        domain = domain.replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0]
        f_name_raw = self.clean_text(first_name)
        l_name_raw = self.clean_text(last_name)
        if not f_name_raw or not domain: return []

        f_joined = f_name_raw.replace(' ', '')
        l_joined = l_name_raw.replace(' ', '')
        f_parts = f_name_raw.split()
        l_parts = l_name_raw.split()
        f_first = f_parts[0] if f_parts else ""
        l_last = l_parts[-1] if l_parts else ""
        f_initial = f_first[0] if f_first else ""
        f_initials_all = "".join([p[0] for p in f_parts])
        l_initial = l_last[0] if l_last else ""

        perms = set()
        if not l_last:
            perms.update([f"{f_joined}@{domain}", f"{f_first}@{domain}"])
            return list(perms)

        patterns = [
            f"{f_first}@{domain}", f"{f_joined}@{domain}", f"{l_last}@{domain}", f"{l_joined}@{domain}",
            f"{f_joined}.{l_joined}@{domain}", f"{f_first}.{l_last}@{domain}", f"{f_joined}{l_joined}@{domain}",
            f"{f_first}{l_last}@{domain}", f"{f_first}_{l_last}@{domain}", f"{f_first}-{l_last}@{domain}",
            f"{f_initial}{l_last}@{domain}", f"{f_initials_all}{l_last}@{domain}", f"{f_initial}.{l_last}@{domain}",
            f"{f_initial}_{l_last}@{domain}", f"{f_first}{l_initial}@{domain}", f"{f_first}.{l_initial}@{domain}",
            f"{l_last}.{f_first}@{domain}", f"{l_last}{f_first}@{domain}"
        ]

        if len(f_parts) > 1:
            f_second = f_parts[1]
            patterns.extend([f"{f_second}@{domain}", f"{f_second}.{l_last}@{domain}", f"{f_first}.{f_second}.{l_last}@{domain}"])

        for p in patterns:
            if p.count('@') == 1 and not p.startswith('.') and not p.startswith('-'): perms.add(p)
        return sorted(list(perms))

    def get_mx_record(self, domain):
        try:
            records = dns.resolver.resolve(domain, 'MX')
            return sorted(records, key=lambda rec: rec.preference)[0].exchange.to_text()
        except:
            return None

    def verify_email(self, email, mx_record):
        try:
            server = smtplib.SMTP(timeout=5) # n8n için hızlı timeout
            server.connect(mx_record, 25)
            server.helo('mail.example.com')
            server.mail('') # Null Sender taktiği
            code, _ = server.rcpt(str(email))
            server.quit()
            return True if code == 250 else False
        except:
            return False # Timeout (Port 25 kapalı) veya hata durumunda False dön

# --- 3. API ENDPOINT (n8n BURAYA İSTEK ATACAK) ---
@app.route('/find_leads', methods=['POST'])
def find_leads():
    data = request.json
    company_name = data.get("firma_adi")
    domain = data.get("domain")

    if not company_name or not domain:
        return jsonify({"status": "error", "message": "Firma adı ve domain zorunludur."}), 400

    print(f"\n[+] YENİ GÖREV ALINDI: {company_name} | {domain}")

    # 1. Scraper'ı çalıştır
    scraper = DDGScraper()
    profiles = scraper.get_profiles(company_name)

    if not profiles:
        print("[-] Yetkili bulunamadı.")
        return jsonify({"status": "failed", "firma_adi": company_name, "reason": "LinkedIn'de yetkili bulunamadı."})

    # 2. Validator'ı çalıştır
    validator = EmailValidator()
    
    # Domain'in posta sunucusunu bir kere bul (Her kişi için tekrar aramamıza gerek yok)
    mx_record = validator.get_mx_record(domain)
    if not mx_record:
        print("[-] Domain MX kaydı yok.")
        return jsonify({"status": "failed", "firma_adi": company_name, "reason": "Firmanın aktif bir mail sunucusu yok."})

    basarili_sonuclar = []

    print(f"[*] {len(profiles)} kişi bulundu. E-mail doğrulaması başlıyor... (Port 25 lokalde kapalıysa Timeout alırız)")
    
    for prof in profiles:
        emails_to_test = validator.generate_permutations(prof['first_name'], prof['last_name'], domain)
        
        for email in emails_to_test:
            if validator.verify_email(email, mx_record):
                # Doğru maili bulduk! Listeye ekle ve bu kişi için diğer ihtimalleri denemeyi bırak
                basarili_sonuclar.append({
                    "Ad": prof['first_name'],
                    "Soyad": prof['last_name'],
                    "Unvan": prof['title'],
                    "Mail": email
                })
                print(f"  ✅ Bulundu: {email}")
                break 

    # 3. n8n'e Sonuç Döndür
    if basarili_sonuclar:
        return jsonify({
            "status": "success",
            "firma_adi": company_name,
            "domain": domain,
            "data": basarili_sonuclar # Bulunan Müşteriler(Yetkili Mailler).csv formatına tam uygun!
        })
    else:
        return jsonify({
            "status": "failed",
            "firma_adi": company_name,
            "reason": "Yetkililer bulundu fakat hiçbir mail adresi doğrulanamadı."
        })

if __name__ == '__main__':
    # Portu 5000 yerine 5001 yaptık
    app.run(host='0.0.0.0', port=5001, debug=True)