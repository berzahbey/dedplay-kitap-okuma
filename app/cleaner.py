import re
from collections import Counter
from app.turkish_numbers import cardinal, ordinal
from app.name_phonetics import apply_phonetics

class TextNormalizer:
    ABBREVIATIONS = {
        # Akademik / mesleki unvanlar
        r'\bYrd\.\s*Doç\.\s*': 'Yardımcı Doçent ',
        r'\bDr\.\s*': 'Doktor ',
        r'\bProf\.\s*': 'Profesör ',
        r'\bDoç\.\s*': 'Doçent ',
        r'\bAv\.\s*': 'Avukat ',
        r'\bMüh\.\s*': 'Mühendis ',
        r'\bNo\.\s*': 'Numara ',
        r'\bvs\.\s*': 've sair, ',
        r'\bv\.b\.\s*': 've benzeri, ',
        r'\bvd\.\s*': 've diğerleri, ',
        r'\bbkz\.\s*': 'bakınız: ',
        r'\bap\.\s*': 'apartmanı, ',

        # Dini önek/sonekler (peygamberler, sahabe, ayet/hadis saygı ifadeleri)
        r'\bHz\.\s*': 'Hazreti ',
        r'\ba\.\s*s\.(?=\s|$|[,.;:])': 'Aleyhisselam',
        r'\bs\.\s*a\.\s*v\.(?=\s|$|[,.;:])': 'Sallallahu Aleyhi ve Sellem',
        r'\bs\.\s*a\.\s*s\.(?=\s|$|[,.;:])': 'Sallallahu Aleyhi ve Sellem',
        r'\br\.\s*a\.(?=\s|$|[,.;:])': 'Radiyallahu Anh',
        r'\bk\.\s*v\.(?=\s|$|[,.;:])': 'Kerremallahu Vecheh',
        r'\bc\.\s*c\.(?=\s|$|[,.;:])': 'Celle Celaluhu',
        r'\bk\.\s*s\.(?=\s|$|[,.;:])': 'Kuddise Sirruh',
    }

    _PAGE_NUM_LINE = re.compile(r'^\s*[-–—]?\s*\d{1,4}\s*[-–—]?\s*(?:[A-Za-zÇĞİÖŞÜçğıöşü]{1,3}\.\s*\d{1,4})?\s*$')
    _SAYFA_LINE = re.compile(r'^\s*(sayfa|page|s\.)\s*\d{1,4}\s*$', re.IGNORECASE)
    _DOT_LEADER = re.compile(r'\.{4,}\s*\d{0,4}\s*$')
    _SHORT_NUMERIC_LINE = re.compile(r'^[\d\s\-–—.,:;()\[\]/]{1,15}$')
    _FOOTNOTE_MARK = re.compile(r'\[\s*\d+\s*\]|[¹²³⁴⁵⁶⁷⁸⁹⁰]+')
    _SYMBOL_NOISE = re.compile(r'[©®™°§¶†‡]')

    @classmethod
    def strip_running_headers(cls, pages):
        """Sayfalar arasında tekrar eden satırları (üstbilgi/altbilgi/sayfa no) siler."""
        if len(pages) < 4:
            return pages
        line_counts = Counter()
        page_lines = []
        for p in pages:
            lines = [l.strip() for l in p.split('\n')]
            page_lines.append(lines)
            for l in set(lines):
                if l and len(l) <= 80:
                    line_counts[l] += 1
        threshold = max(3, int(len(pages) * 0.3))
        noisy = {l for l, c in line_counts.items() if c >= threshold}
        cleaned = []
        for lines in page_lines:
            kept = [l for l in lines if l not in noisy]
            cleaned.append('\n'.join(kept))
        return cleaned

    _CIRCUMFLEX_MAP = str.maketrans({
        'â': 'a', 'Â': 'A',
        'î': 'i', 'Î': 'İ',
        'û': 'u', 'Û': 'U',
    })

    @classmethod
    def normalize_circumflex(cls, text: str) -> str:
        return text.translate(cls._CIRCUMFLEX_MAP)

    _LIST_MARKER = re.compile(r'(?:(?<=^)|(?<=\s))(\d{1,3})\.(?=\s)')
    _STANDALONE_NUM = re.compile(r'\b(\d{1,6})\b')

    @classmethod
    def convert_numbers(cls, text: str) -> str:
        text = cls._LIST_MARKER.sub(lambda m: ordinal(int(m.group(1))), text)
        text = cls._STANDALONE_NUM.sub(lambda m: cardinal(int(m.group(1))), text)
        return text

    @classmethod
    def normalize(cls, text: str) -> str:
        lines = text.split('\n')
        kept_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                kept_lines.append(line)
                continue
            if cls._PAGE_NUM_LINE.match(stripped):
                continue
            if cls._SAYFA_LINE.match(stripped):
                continue
            if cls._DOT_LEADER.search(stripped):
                continue
            if cls._SHORT_NUMERIC_LINE.match(stripped) and any(c.isdigit() for c in stripped):
                continue
            kept_lines.append(line)
        text = '\n'.join(kept_lines)

        text = cls._FOOTNOTE_MARK.sub('', text)
        text = cls._SYMBOL_NOISE.sub('', text)
        text = re.sub(r'\([A-Za-zÇĞİÖŞÜçğıöşü\s\-]+,\s*\d{4}(?:\s*:\s*\d+)?\)', '', text)
        for pattern, replacement in cls.ABBREVIATIONS.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)
        text = re.sub(r'\s+', ' ', text).strip()
        text = cls.convert_numbers(text)
        text = apply_phonetics(text)
        return text
