import unicodedata

import pytest

from app.services.normalisation import (
    COMPOUND_WORDS,
    NORMALISATION_VERSION,
    NUMBER_WORDS,
    NormalisationError,
    normalise,
)


def test_version_is_semver():
    assert NORMALISATION_VERSION == "1.1.0"


# Rule 1: NFC
def test_nfc_composes_alef_madda():
    decomposed = "آم"  # alef + combining madda + meem
    assert normalise(decomposed) == "آم"  # آم
    assert unicodedata.is_normalized("NFC", normalise(decomposed))


# Rule 2: zero-width joiners
def test_removes_zwnj_and_zwj():
    assert normalise("کتاب‌یں‍") == "کتابیں"


# Rule 3: whitespace
def test_collapses_whitespace():
    assert normalise("  ایک \t\n  دو   ") == "ایک دو"


# Rule 4: yeh
def test_arabic_yeh_to_farsi_yeh():
    assert normalise("بيت") == "بیت"


def test_bari_yeh_preserved_word_finally():
    assert normalise("بچے") == "بچے"


def test_bari_yeh_mid_word_becomes_farsi_yeh():
    assert normalise("بےت") == "بیت"


# Rule 5: kaf
def test_arabic_kaf_to_keheh():
    assert normalise("كتاب") == "کتاب"  # کتاب


# Rule 6: heh
def test_heh_to_heh_goal():
    assert normalise("وه") == "وہ"  # وہ


# Rule 7: chahiye
@pytest.mark.parametrize("variant", ["چاہئے", "چاہیئے", "چاہیے", "چاهئے"])
def test_chahiye_variants_collapse(variant):
    assert normalise(f"مجھے {variant}") == "مجھے چاہیے"


# Rule 8: diacritics
def test_strips_diacritics():
    with_marks = "مَحَبَّت"  # مَحَبَّت
    assert normalise(with_marks) == "محبت"


def test_strips_zer_pesh_jazm_khari_zabar():
    assert normalise("اِسْلُمٰ") == "اسلم"


# Rule 9: punctuation
def test_strips_urdu_punctuation():
    assert normalise("کیا، تم آئے؟ ہاں۔") == "کیا تم آئے ہاں"


# Rule 10: digits
def test_ascii_digits_to_words():
    assert normalise("5 بچے") == "پانچ بچے"


def test_urdu_digits_to_words():
    assert normalise("۲۵ کتابیں") == "پچیس کتابیں"


def test_digits_attached_to_word_are_split():
    assert normalise("100روپے") == "سو روپے"


def test_number_table_covers_0_to_100():
    assert sorted(NUMBER_WORDS) == list(range(101))


@pytest.mark.parametrize(
    "digits, words",
    [
        ("1947", "انیس سو سینتالیس"),  # years in the built-in passages
        ("1857", "اٹھارہ سو ستاون"),
        ("1906", "انیس سو چھ"),
        ("1979", "انیس سو اناسی"),
        ("1800", "اٹھارہ سو"),
        ("2002", "دو ہزار دو"),
        ("2007", "دو ہزار سات"),
        ("2026", "دو ہزار چھبیس"),
        ("200", "دو سو"),
        ("101", "ایک سو ایک"),
        ("1000", "ایک ہزار"),
        ("1100", "گیارہ سو"),
        ("2100", "دو ہزار ایک سو"),
        ("2500", "دو ہزار پانچ سو"),
        ("9999", "نو ہزار نو سو ننانوے"),
        ("1050", "ایک ہزار پچاس"),
    ],
)
def test_numbers_above_100(digits, words):
    assert normalise(digits) == words


def test_urdu_digit_year():
    assert normalise("۱۹۴۷ میں") == "انیس سو سینتالیس میں"


def test_numbers_above_9999_raise():
    with pytest.raises(NormalisationError):
        normalise("10000")


# Rule 11: compound verbs
def test_compound_verb_segmented():
    assert normalise("وہ گھر آگیا") == "وہ گھر آ گیا"


def test_compound_only_matches_whole_words():
    # A compound key embedded inside a longer word is left alone.
    assert normalise("ہوگیاں") == "ہوگیاں"


def test_compound_table_is_already_normalised():
    for joined, split in COMPOUND_WORDS.items():
        assert normalise(split) == split
        assert normalise(joined) == split


# Combined
def test_insertion_tokens_survive():
    assert normalise("ایک [unintelligible] دو [code-switch]") == "ایک [unintelligible] دو [code-switch]"


def test_idempotent():
    raw = "  كتاب  وه چاہئے۔ 7 "
    once = normalise(raw)
    assert normalise(once) == once == "کتاب وہ چاہیے سات"
