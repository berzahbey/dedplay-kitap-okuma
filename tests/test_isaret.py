"""19 Ekim: yildiz ve sus isaretleri seslendirmede okunmaz; isaretsiz metin degismez.
  docker run --rm -v "$PWD":/k -w /k -e PYTHONPATH=/k berzahbey/dedplay-kitap-okuma:latest python tests/test_isaret.py"""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from app.cleaner import TextNormalizer as T
kalan = 0
def bak(ad, girdi, beklenen):
    global kalan
    cikan = T.normalize(girdi)
    ok = cikan == beklenen
    kalan += not ok
    print(("GECTI " if ok else "KALDI ") + ad + ("" if ok else f"\n   cikan:    {cikan!r}\n   beklenen: {beklenen!r}"))
bak("atif (*)", "Envâr Neşriyat Çok kıymetlidir (*) diyor.", "Envâr Neşriyat Çok kıymetlidir diyor.")
bak("not etiketi (*):", "Dokuzuncu Nokta: (*): Bu gibi şifreler.", "Dokuzuncu Nokta: Bu gibi şifreler.")
bak("terim isareti", "ummu'l-veled* in satılabileceği", "ummu'l-veled in satılabileceği")
bak("kapanis yerine yildiz", "söz başkaları içindir*. Çünkü", "söz başkaları içindir. Çünkü")
bak("kelime ici yildiz", "o aşk ve sev* gi harekete", "o aşk ve sev gi harekete")
bak("Arapca misra", "قَدِ اْمَتَلاَتْ * مِنَ الْمَحَارِمِ", "قَدِ اْمَتَلاَتْ \u060c مِنَ الْمَحَارِمِ")
bak("ayrac * * *", "Birinci kısım bitti. * * * İkinci kısım.", "Birinci kısım bitti. İkinci kısım.")
bak("madde imi", "• Birinci ★ ikinci", "Birinci ikinci")
bak("ters tirnak", "Kur`an okundu", "Kur'an okundu")
# isaretsiz metinde yildiz kalmaz; ornekler
ornekler = ["Elif-Lâm-Mîm. Bu, kendisinde hiçbir şüphe bulunmayan Kitap’tır.",
            "Hz. Ömer (r.a.) 23 yaşında, s. 45'te: \"Ey âdemoğlu!\" dedi; 1. madde.",
            "بِسْمِ اللّهِ الرَّحْمنِ الرَّحِيمِ اَلْحَمْدُ لِلّهِ", "Fiyat %20 arttı & düştü + 5 = 10, 3/4 oranında."]
import re
for o in ornekler:
    assert not re.search(r"[*•★]", T.normalize(o))
print("SONUC: HEPSI GECTI" if not kalan else f"SONUC: {kalan} KALDI")
