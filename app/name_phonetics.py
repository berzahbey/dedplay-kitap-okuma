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
}

def apply_phonetics(text: str) -> str:
    import re
    for name, phonetic in PHONETIC_OVERRIDES.items():
        text = re.sub(rf'\b{re.escape(name)}\b', phonetic, text)
    return text
