"""Annex E.1 Layer 2 error tag taxonomy (closed list, fixed order)."""

from typing import NamedTuple


class ErrorTag(NamedTuple):
    code: str
    label: str
    counts_as_error: bool | None  # None = recorded only (INS)


ERROR_TAGS: tuple[ErrorTag, ...] = (
    ErrorTag("SUB", "Substitution", True),
    ErrorTag("MIS", "Mispronunciation", True),
    ErrorTag("OMI", "Omission", True),
    ErrorTag("INS", "Insertion", None),
    ErrorTag("PRO", "Prompted", True),
    ErrorTag("SC", "Self-correction", False),
    ErrorTag("REP", "Repetition", False),
    ErrorTag("HES", "Hesitation", False),
    ErrorTag("PAR", "Partial word", True),
    ErrorTag("CS", "Code-switch", True),
    ErrorTag("TRN", "Transposition", False),
    ErrorTag("UNI", "Unintelligible", True),
)

ERROR_TAG_CODES = tuple(t.code for t in ERROR_TAGS)
ERROR_CODES = frozenset(t.code for t in ERROR_TAGS if t.counts_as_error is True)
NON_ERROR_CODES = frozenset(t.code for t in ERROR_TAGS if t.counts_as_error is False)
INSERTION_CODE = "INS"
