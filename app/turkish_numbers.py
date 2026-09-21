# Türkçe sayıları yazıya çeviren yardımcı fonksiyonlar.
# Piper'ın "1.", "6" gibi rakamları yanlış/tutarsız okumasını önlemek için
# TTS'e göndermeden önce sayıları kelimeye çeviriyoruz.

_ONES = ["", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz"]
_TENS = ["", "on", "yirmi", "otuz", "kırk", "elli", "altmış", "yetmiş", "seksen", "doksan"]

_ORD_ONES = ["", "birinci", "ikinci", "üçüncü", "dördüncü", "beşinci",
             "altıncı", "yedinci", "sekizinci", "dokuzuncu"]
_ORD_TENS = ["", "onuncu", "yirminci", "otuzuncu", "kırkıncı", "ellinci",
             "altmışıncı", "yetmişinci", "sekseninci", "doksanıncı"]


def cardinal(n: int) -> str:
    if n == 0:
        return "sıfır"
    parts = []
    if n >= 1000:
        th = n // 1000
        parts.append("bin" if th == 1 else f"{cardinal(th)} bin")
        n %= 1000
    if n >= 100:
        h = n // 100
        parts.append("yüz" if h == 1 else f"{_ONES[h]} yüz")
        n %= 100
    if n >= 10:
        parts.append(_TENS[n // 10])
        n %= 10
    if n > 0:
        parts.append(_ONES[n])
    return " ".join(parts)


def ordinal(n: int) -> str:
    if n <= 0:
        return "sıfırıncı"
    if n < 10:
        return _ORD_ONES[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        return _ORD_TENS[tens] if ones == 0 else f"{_TENS[tens]} {_ORD_ONES[ones]}"
    base = (n // 100) * 100
    rem = n % 100
    return cardinal(base) + "üncü" if rem == 0 else f"{cardinal(base)} {ordinal(rem)}"
