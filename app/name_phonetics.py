# Batılı özel isimlerin Türkçe okunuşa yakın fonetik yazılışları.
# Piper Türkçe sesi bu isimleri OLDUĞU GİBİ değil, burada yazıldığı
# şekliyle okuyacağı için doğru telaffuza yakın çıkar.
# Yeni bir isimle karşılaşırsan buraya bir satır eklemen yeterli.

PHONETIC_OVERRIDES = {
    "Bacon": "Beykın",
    "Newton": "Nyutın",
    "Descartes": "Dekart",
    "Voltaire": "Volter",
    "Rousseau": "Ruso",
    "Montesquieu": "Montskiyö",
    "Diderot": "Didro",
    "Hegel": "Heygel",
    "Nietzsche": "Niçe",
    "Marx": "Marks",
    "Engels": "Engıls",
    "Freud": "Froyd",
    "Darwin": "Darvin",
    "Comte": "Kont",
    "Durkheim": "Dürkaym",
    "Weber": "Veber",
    "Locke": "Lok",
    "Hume": "Hyum",
    "Machiavelli": "Makyaveli",
    "Spinoza": "Spinoza",
    "Kant": "Kant",
    "Columbia": "Kolombiya",
    "Harvard": "Harvırd",
    "Princeton": "Prinstın",
    "Yale": "Yeyl",
    "Oxford": "Oksford",
    "Cambridge": "Keymbriç",
    "Chomsky": "Çomski",
    "Foucault": "Fuko",
    ".com": " kom",
    ".net": " net",
    ".org": " org",
    ".gov": " gav",
}

def apply_phonetics(text: str) -> str:
    import re
    for name, phonetic in PHONETIC_OVERRIDES.items():
        if name.startswith('.'):
            # ".com" gibi noktayla başlayan kalıplar: kelime sınırı (\b)
            # nokta karakteriyle uyumsuz olduğu için ayrı işlenir.
            text = re.sub(re.escape(name), phonetic, text)
        else:
            text = re.sub(rf'\b{re.escape(name)}\b', phonetic, text)
    return text
