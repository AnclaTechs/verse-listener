"""
core/bible_detector.py
Detects Bible verse references in transcribed text using comprehensive
book name/abbreviation mappings and flexible regex patterns.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# ── Bible book database ──────────────────────────────────────────────────────
# Maps canonical name → list of accepted spellings/abbreviations (all lowercase)
BIBLE_BOOKS: dict[str, list[str]] = {
    # Old Testament
    "Genesis":        ["genesis", "gen", "ge", "gn"],
    "Exodus":         ["exodus", "exo", "ex", "exod"],
    "Leviticus":      ["leviticus", "lev", "le", "lv"],
    "Numbers":        ["numbers", "num", "nu", "nb"],
    "Deuteronomy":    ["deuteronomy", "deut", "deu", "dt", "de"],
    "Joshua":         ["joshua", "josh", "jos", "jsh"],
    "Judges":         ["judges", "judg", "jdg", "jg", "jdgs"],
    "Ruth":           ["ruth", "rut", "rth"],
    "1 Samuel":       ["1 samuel", "1samuel", "1sam", "1sa", "1sm", "i samuel", "first samuel"],
    "2 Samuel":       ["2 samuel", "2samuel", "2sam", "2sa", "2sm", "ii samuel", "second samuel"],
    "1 Kings":        ["1 kings", "1kings", "1kgs", "1ki", "i kings", "first kings"],
    "2 Kings":        ["2 kings", "2kings", "2kgs", "2ki", "ii kings", "second kings"],
    "1 Chronicles":   ["1 chronicles", "1chronicles", "1chr", "1ch", "i chronicles", "first chronicles"],
    "2 Chronicles":   ["2 chronicles", "2chronicles", "2chr", "2ch", "ii chronicles", "second chronicles"],
    "Ezra":           ["ezra", "ezr"],
    "Nehemiah":       ["nehemiah", "neh", "ne"],
    "Esther":         ["esther", "est", "esth"],
    "Job":            ["job", "jb"],
    "Psalms":         ["psalms", "psalm", "psa", "ps", "pss"],
    "Proverbs":       ["proverbs", "prov", "pro", "prv", "pv"],
    "Ecclesiastes":   ["ecclesiastes", "eccl", "ecc", "qoh", "eccles"],
    "Song of Solomon":["song of solomon", "song of songs", "song", "sos", "ss", "cant", "canticles"],
    "Isaiah":         ["isaiah", "isa", "is"],
    "Jeremiah":       ["jeremiah", "jer", "je", "jr"],
    "Lamentations":   ["lamentations", "lam", "la"],
    "Ezekiel":        ["ezekiel", "ezek", "eze", "ezk"],
    "Daniel":         ["daniel", "dan", "da", "dn"],
    "Hosea":          ["hosea", "hos", "ho"],
    "Joel":           ["joel", "jol", "joe", "jl"],
    "Amos":           ["amos", "amo", "am"],
    "Obadiah":        ["obadiah", "obad", "oba", "ob"],
    "Jonah":          ["jonah", "jon", "jnh"],
    "Micah":          ["micah", "mic", "mi"],
    "Nahum":          ["nahum", "nah", "na"],
    "Habakkuk":       ["habakkuk", "hab", "hb"],
    "Zephaniah":      ["zephaniah", "zeph", "zep", "zp"],
    "Haggai":         ["haggai", "hag", "hg"],
    "Zechariah":      ["zechariah", "zech", "zec", "zc"],
    "Malachi":        ["malachi", "mal", "ml"],
    # New Testament
    "Matthew":        ["matthew", "matt", "mat", "mt"],
    "Mark":           ["mark", "mrk", "mar", "mk", "mr"],
    "Luke":           ["luke", "luk", "lk"],
    "John":           ["john", "joh", "jn", "jhn"],
    "Acts":           ["acts", "act", "ac"],
    "Romans":         ["romans", "rom", "ro", "rm"],
    "1 Corinthians":  ["1 corinthians", "1corinthians", "1cor", "1co", "i corinthians", "first corinthians"],
    "2 Corinthians":  ["2 corinthians", "2corinthians", "2cor", "2co", "ii corinthians", "second corinthians"],
    "Galatians":      ["galatians", "gal", "ga"],
    "Ephesians":      ["ephesians", "eph", "ephes"],
    "Philippians":    ["philippians", "phil", "php", "pp"],
    "Colossians":     ["colossians", "col", "co"],
    "1 Thessalonians":["1 thessalonians", "1thessalonians", "1thess", "1th", "i thessalonians", "first thessalonians"],
    "2 Thessalonians":["2 thessalonians", "2thessalonians", "2thess", "2th", "ii thessalonians", "second thessalonians"],
    "1 Timothy":      ["1 timothy", "1timothy", "1tim", "1ti", "i timothy", "first timothy"],
    "2 Timothy":      ["2 timothy", "2timothy", "2tim", "2ti", "ii timothy", "second timothy"],
    "Titus":          ["titus", "tit", "ti"],
    "Philemon":       ["philemon", "phlm", "phm", "pm"],
    "Hebrews":        ["hebrews", "heb", "he"],
    "James":          ["james", "jas", "jm"],
    "1 Peter":        ["1 peter", "1peter", "1pet", "1pe", "i peter", "first peter"],
    "2 Peter":        ["2 peter", "2peter", "2pet", "2pe", "ii peter", "second peter"],
    "1 John":         ["1 john", "1john", "1jn", "1jo", "i john", "first john"],
    "2 John":         ["2 john", "2john", "2jn", "2jo", "ii john", "second john"],
    "3 John":         ["3 john", "3john", "3jn", "3jo", "iii john", "third john"],
    "Jude":           ["jude", "jud", "jd"],
    "Revelation":     ["revelation", "revelations", "rev", "re", "rv", "the revelation"],
}

# Build reverse lookup: abbreviation → canonical name
_ABBREV_TO_CANONICAL: dict[str, str] = {}
for canonical, aliases in BIBLE_BOOKS.items():
    for alias in aliases:
        _ABBREV_TO_CANONICAL[alias.lower()] = canonical

# Sorted by length (longest first) so longer matches win
_SORTED_ALIASES = sorted(_ABBREV_TO_CANONICAL.keys(), key=len, reverse=True)

# Escape aliases for regex use
_ALIAS_PATTERN = "|".join(re.escape(a) for a in _SORTED_ALIASES)

# ── Verse reference patterns ──────────────────────────────────────────────────
# Supports:
#   Genesis 5:2
#   Gen 5:2
#   Genesis chapter 5 verse 2
#   Gen ch 5 v 2
#   Genesis 5 v 2-4
#   book of Romans chapter 8 verses 28 through 30
#   Romans 8:28-30

_BOOK_RE   = rf"(?:book\s+of\s+)?({_ALIAS_PATTERN})"
_CH_RE     = r"(?:chapter|chap|ch\.?)?\s*"
_NUM_RE    = r"(\d+)"
_SEP_RE    = r"(?:\s*:\s*|\s+(?:verses?|ver\.?|v\.?)\s*)"   # ":" or "verse(s)/v"
_END_RE    = r"(?:\s*[-–—]\s*(\d+)|(?:\s+(?:through|thru|to|and)\s+(\d+)))?"  # optional end verse
_VS_INTRO  = r"(?:\s+(?:verses?|ver\.?|v\.?)\s*)"      # "verses" before range

VERSE_PATTERN = re.compile(
    rf"""
    (?<!\w)                     # not preceded by word char (avoid mid-word matches)
    {_BOOK_RE}                  # (1) book name / abbreviation
    [\s,]+                      # separator
    {_CH_RE}                    # optional "chapter"
    {_NUM_RE}                   # (2) chapter number
    (?:                         # optional verse part
        {_SEP_RE}               # separator (: or "verse")
        {_NUM_RE}               # (3) start verse
        {_END_RE}               # (4)(5) optional end verse
    )?
    """,
    re.IGNORECASE | re.VERBOSE,
)


@dataclass
class VerseMatch:
    raw_text: str          # matched substring in transcript
    book: str              # canonical book name
    chapter: int
    verse_start: Optional[int] = None
    verse_end: Optional[int] = None
    start_pos: int = 0     # character position in transcript
    end_pos: int = 0
    confidence: float = 1.0

    @property
    def reference(self) -> str:
        """Return a clean verse reference string, e.g. 'Romans 8:28-30'."""
        ref = f"{self.book} {self.chapter}"
        if self.verse_start is not None:
            ref += f":{self.verse_start}"
            if self.verse_end is not None:
                ref += f"-{self.verse_end}"
        return ref

    @property
    def easyworship_query(self) -> str:
        """Return the string to type into EasyWorship search box."""
        return self.reference


class BibleDetector:
    """Scans transcription text for Bible verse references."""

    def __init__(self):
        self._seen: set[str] = set()   # avoid duplicate detections per session

    def reset(self):
        self._seen.clear()

    def detect(self, text: str, deduplicate: bool = True) -> list[VerseMatch]:
        """
        Return a list of VerseMatch objects found in *text*.
        If deduplicate=True, skip references already returned this session.
        """
        matches: list[VerseMatch] = []

        for m in VERSE_PATTERN.finditer(text):
            raw_book = m.group(1).lower()
            canonical = _ABBREV_TO_CANONICAL.get(raw_book)
            if not canonical:
                continue

            chapter = int(m.group(2))
            verse_start = int(m.group(3)) if m.group(3) else None
            # groups 4 & 5 are the two alternate end-verse captures
            verse_end_raw = m.group(4) or m.group(5)
            verse_end = int(verse_end_raw) if verse_end_raw else None

            vm = VerseMatch(
                raw_text=m.group(0).strip(),
                book=canonical,
                chapter=chapter,
                verse_start=verse_start,
                verse_end=verse_end,
                start_pos=m.start(),
                end_pos=m.end(),
            )

            if deduplicate and vm.reference in self._seen:
                continue

            if deduplicate:
                self._seen.add(vm.reference)

            matches.append(vm)
            logger.debug("Detected verse: %s", vm.reference)

        return matches
