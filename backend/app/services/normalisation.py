"""Annex E.4 text normalisation for Urdu transcripts.

Pure function, no I/O. Bump NORMALISATION_VERSION whenever any rule or table
below changes, since exported data records the version it was produced with.
"""

import re
import unicodedata

NORMALISATION_VERSION = "1.0.0"

# Rule 2
_ZERO_WIDTH = str.maketrans("", "", "‌‍")

# Rules 4-6: character mappings onto the canonical Urdu code points.
ARABIC_YEH = "ي"
FARSI_YEH = "ی"
BARI_YEH = "ے"
_CHAR_MAP = str.maketrans(
    {
        ARABIC_YEH: FARSI_YEH,
        "ك": "ک",  # Arabic kaf -> keheh
        "ه": "ہ",  # heh -> heh goal
    }
)
# Bari yeh is only legitimate word-finally; elsewhere it becomes Farsi yeh.
_NON_FINAL_BARI_YEH = re.compile(BARI_YEH + r"(?=\w)")

# Rule 7: hamza-sequence spellings of "chahiye" (already in post-rule-6 form).
CHAHIYE = "چاہیے"  # چاہیے
_CHAHIYE_VARIANTS = (
    "چاہئے",  # چاہئے
    "چاہیئے",  # چاہیئے
)
_CHAHIYE_RE = re.compile(r"(?<!\w)(?:" + "|".join(_CHAHIYE_VARIANTS) + r")(?!\w)")

# Rule 8: zabar, pesh, zer, tashdeed, jazm, khari zabar.
_DIACRITICS = str.maketrans("", "", "َُِّْٰ")

# Rule 9: Urdu full stop, Arabic comma, Arabic question mark.
_PUNCTUATION = str.maketrans("", "", "۔،؟")

# Rule 10: digits (ASCII and Urdu-Indic) -> Urdu number words, 0-100.
_URDU_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
_DIGIT_RUN = re.compile(r"[0-9۰-۹]+")
NUMBER_WORDS: dict[int, str] = {
    0: "صفر", 1: "ایک", 2: "دو", 3: "تین", 4: "چار", 5: "پانچ", 6: "چھ", 7: "سات", 8: "آٹھ", 9: "نو",
    10: "دس", 11: "گیارہ", 12: "بارہ", 13: "تیرہ", 14: "چودہ", 15: "پندرہ", 16: "سولہ", 17: "سترہ",
    18: "اٹھارہ", 19: "انیس", 20: "بیس", 21: "اکیس", 22: "بائیس", 23: "تئیس", 24: "چوبیس", 25: "پچیس",
    26: "چھبیس", 27: "ستائیس", 28: "اٹھائیس", 29: "انتیس", 30: "تیس", 31: "اکتیس", 32: "بتیس",
    33: "تینتیس", 34: "چونتیس", 35: "پینتیس", 36: "چھتیس", 37: "سینتیس", 38: "اڑتیس", 39: "انتالیس",
    40: "چالیس", 41: "اکتالیس", 42: "بیالیس", 43: "تینتالیس", 44: "چوالیس", 45: "پینتالیس",
    46: "چھیالیس", 47: "سینتالیس", 48: "اڑتالیس", 49: "انچاس", 50: "پچاس", 51: "اکاون", 52: "باون",
    53: "ترپن", 54: "چون", 55: "پچپن", 56: "چھپن", 57: "ستاون", 58: "اٹھاون", 59: "انسٹھ", 60: "ساٹھ",
    61: "اکسٹھ", 62: "باسٹھ", 63: "تریسٹھ", 64: "چونسٹھ", 65: "پینسٹھ", 66: "چھیاسٹھ", 67: "سڑسٹھ",
    68: "اڑسٹھ", 69: "انہتر", 70: "ستر", 71: "اکہتر", 72: "بہتر", 73: "تہتر", 74: "چوہتر", 75: "پچھتر",
    76: "چھہتر", 77: "ستتر", 78: "اٹھہتر", 79: "اناسی", 80: "اسی", 81: "اکیاسی", 82: "بیاسی",
    83: "تراسی", 84: "چوراسی", 85: "پچاسی", 86: "چھیاسی", 87: "ستاسی", 88: "اٹھاسی", 89: "نواسی",
    90: "نوے", 91: "اکانوے", 92: "بانوے", 93: "ترانوے", 94: "چورانوے", 95: "پچانوے", 96: "چھیانوے",
    97: "ستانوے", 98: "اٹھانوے", 99: "ننانوے", 100: "سو",
}

# Rule 11: joined compound verb forms -> canonical space-separated segmentation.
# Keys must already be in post-rule-4 form (e.g. no mid-word bari yeh).
COMPOUND_WORDS: dict[str, str] = {
    "کرلیا": "کر لیا",
    "کردیا": "کر دیا",
    "کرلی": "کر لی",
    "کردی": "کر دی",
    "ہوگیا": "ہو گیا",
    "ہوگئی": "ہو گئی",
    "ہوگئے": "ہو گئے",
    "چلاگیا": "چلا گیا",
    "چلاگئی": "چلا گئی",
    "آگیا": "آ گیا",
    "آگئی": "آ گئی",
    "دیکھلیا": "دیکھ لیا",
    "سوگیا": "سو گیا",
}
_COMPOUND_RE = re.compile(
    r"(?<!\w)(?:" + "|".join(sorted(map(re.escape, COMPOUND_WORDS), key=len, reverse=True)) + r")(?!\w)"
)

_WHITESPACE = re.compile(r"\s+")


class NormalisationError(ValueError):
    """Raised when input contains something the rules cannot normalise."""


def _collapse_ws(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip()


def _number_to_words(match: re.Match[str]) -> str:
    value = int(match.group(0).translate(_URDU_DIGITS))
    if value not in NUMBER_WORDS:
        raise NormalisationError(f"number {value} is outside the supported range 0-100; write it in words")
    return f" {NUMBER_WORDS[value]} "


def normalise(text: str) -> str:
    text = unicodedata.normalize("NFC", text)  # 1
    text = text.translate(_ZERO_WIDTH)  # 2
    text = _collapse_ws(text)  # 3
    text = text.translate(_CHAR_MAP)  # 4 (yeh), 5 (kaf), 6 (heh)
    text = _NON_FINAL_BARI_YEH.sub(FARSI_YEH, text)  # 4 (bari yeh)
    text = _CHAHIYE_RE.sub(CHAHIYE, text)  # 7
    text = text.translate(_DIACRITICS)  # 8
    text = text.translate(_PUNCTUATION)  # 9
    text = _DIGIT_RUN.sub(_number_to_words, text)  # 10
    text = _COMPOUND_RE.sub(lambda m: COMPOUND_WORDS[m.group(0)], text)  # 11
    # Stripping punctuation and expanding digits can leave stray spaces.
    return _collapse_ws(text)
