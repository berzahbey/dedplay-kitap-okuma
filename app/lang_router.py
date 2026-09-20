import re
from langdetect import detect, DetectorFactory, LangDetectException

DetectorFactory.seed = 0

ARABIC_RE = re.compile(r'[\u0600-\u06FF]')
SENTENCE_SPLIT_RE = re.compile(r'(?<=[\.\!\?؟])\s+')
DEFAULT_LANG = 'tr'
MIN_LEN_FOR_DETECT = 12

def split_sentences(text: str):
    text = text.strip()
    if not text:
        return []
    parts = SENTENCE_SPLIT_RE.split(text)
    return [p.strip() for p in parts if p.strip()]

def detect_lang(sentence: str) -> str:
    letters = re.findall(r'\w', sentence, re.UNICODE)
    if letters:
        arabic_count = len(ARABIC_RE.findall(sentence))
        if arabic_count / max(len(letters), 1) > 0.25:
            return 'ar'
    if len(sentence) < MIN_LEN_FOR_DETECT:
        return DEFAULT_LANG
    try:
        lang = detect(sentence)
    except LangDetectException:
        return DEFAULT_LANG
    if lang == 'en':
        return 'en'
    if lang == 'fr':
        return 'fr'
    return DEFAULT_LANG

def group_by_language(text: str):
    """Metni cümlelere böler, her cümlenin dilini tespit eder,
    ardışık aynı-dil cümleleri tek blokta birleştirir."""
    sentences = split_sentences(text)
    blocks = []
    current_lang = None
    current_parts = []
    for s in sentences:
        lang = detect_lang(s)
        if lang == current_lang:
            current_parts.append(s)
        else:
            if current_parts:
                blocks.append((current_lang, ' '.join(current_parts)))
            current_lang = lang
            current_parts = [s]
    if current_parts:
        blocks.append((current_lang, ' '.join(current_parts)))
    return blocks
