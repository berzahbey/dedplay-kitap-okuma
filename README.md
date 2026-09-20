# Dedplay Kitap Okuma

Yerel, çok dilli (TR/AR/EN/FR) sesli kitap dönüştürücü. EPUB/PDF yükler,
Piper TTS ile seslendirir, bölümleri otomatik olarak tek bir .m4b sesli
kitap dosyasında birleştirir (bölüm işaretleriyle).

## Kurulum

```bash
git clone https://github.com/berzahbey/dedplay-kitap-okuma.git
cd dedplay-kitap-okuma
docker compose up -d
```

Arayüz: `http://<sunucu-ip>:8011`

## Özellikler
- EPUB/PDF -> otomatik bölüm tespiti
- Cümle bazlı dil tespiti (TR/AR/EN/FR) ve her dile uygun Piper sesi
- Sayfa numarası / tekrarlayan üstbilgi-altbilgi temizliği
- Özel isim telaffuz sözlüğü (app/name_phonetics.py)
- Şapkalı harf (â, î, û) normalizasyonu
- İşlem bitince otomatik .m4b (bölüm işaretli sesli kitap) oluşturma
