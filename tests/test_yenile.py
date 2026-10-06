"""Dedplay Stüdyo tur 2/C: aynı kitap (EPUB) düzeltilip yeniden gönderilince yalnız metni değişen bölümün sesi yeniden
üretilir; değişmeyenin sesi korunur, artık olmayan bölüm kalkar, M4B yeniden kurulur. Ses üretimi taklit edilir (Piper çalışmaz).
  docker run --rm -v "$PWD":/k -w /k berzahbey/dedplay-kitap-okuma:latest python tests/test_yenile.py"""
import os, sys, tempfile, types
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
for ad in ("piper", "pytesseract", "pydub"):          # yerelde bu paketler olmayabilir: ses üretimi zaten taklit
    if ad not in sys.modules:
        try:
            __import__(ad)
        except Exception:
            m = types.ModuleType(ad); m.PiperVoice = object; m.AudioSegment = object; sys.modules[ad] = m
kok = Path(tempfile.mkdtemp())
import app.main as M
M.BOOKS_DIR, M.TEXT_DIR, M.AUDIO_DIR = kok / "b", kok / "t", kok / "a"
for d in (M.BOOKS_DIR, M.TEXT_DIR, M.AUDIO_DIR):
    d.mkdir()
uretilen = []


class Havuz:  # ProcessPoolExecutor yerine: aynı süreçte, sahte mp3
    def __init__(self, *a, **k): pass
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def submit(self, f, text, out):
        out.write_text("ses:" + text[:20]); uretilen.append(out.stem)
        import concurrent.futures as cf
        fu = cf.Future(); fu.set_result(None); return fu


M.ProcessPoolExecutor = Havuz
M.as_completed = lambda fs: list(fs)
M.build_audiobook = lambda d, t: ((d / f"{t}.m4b").write_text("m4b"), d / f"{t}.m4b")[1]
B = []


def ok(k, ad):
    B.append(bool(k)); print(("GECTI " if k else "KALDI ") + ad)


def epub_yaz(bolumler):
    from ebooklib import epub
    book = epub.EpubBook(); book.set_identifier("x"); book.set_title("Deneme"); book.set_language("tr")
    chs = []
    for i, (bas, govde) in enumerate(bolumler, 1):
        ch = epub.EpubHtml(title=str(i), file_name=f"b{i}.xhtml", lang="tr")
        ch.content = f"<html><body><h1>{bas}</h1><p>{govde}</p></body></html>"
        book.add_item(ch); chs.append(ch)
    book.add_item(epub.EpubNcx()); book.add_item(epub.EpubNav()); book.spine = chs
    epub.write_epub(str(M.BOOKS_DIR / "Deneme.epub"), book)


uzun = " Bu cümle bölümü yüz harften uzun yapmak için yazılmıştır ve seslendirilir." * 3
epub_yaz([("Birinci Bölüm", "Ilk metin." + uzun), ("İkinci Bölüm", "İkinci metin." + uzun), ("Üçüncü", "Üçüncü metin." + uzun)])
M.process_book_pipeline("Deneme.epub")
ses = M.AUDIO_DIR / "Deneme"
ok(len(uretilen) == 3 and (ses / "Deneme.m4b").exists(), f"ilk gönderim: 3 bölüm okundu {uretilen}")
ok(any("Birinci_B" in p.name for p in ses.glob("*.mp3")), "bölüm adı başlıktan (M4B bölüm adı)")
uretilen.clear()
epub_yaz([("Birinci Bölüm", "Ilk metin." + uzun), ("İkinci Bölüm", "İkinci metin DÜZELTİLDİ." + uzun)])
M.process_book_pipeline("Deneme.epub")
ok(len(uretilen) == 1 and uretilen[0].startswith("Bolum_002"), f"düzeltmeden sonra yalnız değişen bölüm okundu {uretilen}")
ok(len(list(ses.glob("*.mp3"))) == 2 and len(list((M.TEXT_DIR / "Deneme").glob("*.txt"))) == 2, "artık olmayan bölüm kalktı")
ok("DÜZELTİLDİ" in (M.TEXT_DIR / "Deneme" / (uretilen[0] + ".txt")).read_text(encoding="utf-8"), "yeni metin kullanıldı")
ok(M.job_status["Deneme.epub"]["status"] == "completed" and (ses / "Deneme.m4b").exists(), "M4B yeniden kuruldu")
print("SONUC:", "HEPSI GECTI" if all(B) else f"{B.count(False)} TEST KALDI")
sys.exit(0 if all(B) else 1)
