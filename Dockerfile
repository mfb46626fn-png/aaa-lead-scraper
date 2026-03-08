# Hafif bir Python imajı kullanıyoruz
FROM python:3.9-slim

# Uygulama kodlarını konteynerin içine kopyala
WORKDIR /app
COPY . .

# Gerekli kütüphaneleri yükle
RUN pip install --no-cache-dir -r requirements.txt

# Uygulamayı başlat
CMD ["python", "app.py"]