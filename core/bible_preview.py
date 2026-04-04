"""
core/bible_preview.py
Loads local Bible canon files for offline verse preview in the UI.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_REFERENCE_RE = re.compile(
    r"^(?P<book>.+?)\s+(?P<chapter>\d+)(?::(?P<start>\d+)(?:-(?P<end>\d+))?)?$"
)
_CHAPTER_KEY_RE = re.compile(r"^(?P<book>.+?)\s+(?P<chapter>\d+):(?P<verse>\d+)$")


@dataclass
class BiblePreview:
    edition: str
    reference: str
    body: str
    found: bool = True
    note: str = ""


class BiblePreviewLibrary:
    def __init__(self, root: Optional[Path] = None):
        self.root = root or Path(__file__).resolve().parent.parent / "canons"
        self._cache: dict[str, dict[str, str]] = {}

    def available_editions(self) -> list[str]:
        if not self.root.exists():
            return []

        editions: list[str] = []
        for path in sorted(self.root.iterdir()):
            if path.is_dir() and (path / "verses.json").exists():
                editions.append(path.name)
        return editions

    def get_preview(self, reference: str, requested_edition: str) -> BiblePreview:
        editions = self.available_editions()
        if not editions:
            return BiblePreview(
                edition="—",
                reference=reference,
                body="No local canon files were found. Add a verses.json file under canons/<EDITION>/.",
                found=False,
                note="Preview unavailable",
            )

        edition, edition_note = self._resolve_edition(requested_edition, editions)
        verses = self._load_edition(edition)
        parsed = self._parse_reference(reference)
        if not parsed:
            return BiblePreview(
                edition=edition,
                reference=reference,
                body="This reference format cannot be previewed yet.",
                found=False,
                note=edition_note or "Preview unavailable",
            )

        book, chapter, verse_start, verse_end = parsed
        if verse_start is None:
            return self._preview_chapter(book, chapter, verses, edition, reference, edition_note)
        return self._preview_range(
            book,
            chapter,
            verse_start,
            verse_end or verse_start,
            verses,
            edition,
            reference,
            edition_note,
        )

    def _resolve_edition(self, requested_edition: str, editions: list[str]) -> tuple[str, str]:
        requested = requested_edition.strip()
        if requested:
            for edition in editions:
                if edition.lower() == requested.lower():
                    return edition, ""

        fallback = editions[0]
        if requested:
            return fallback, f"Using {fallback}; {requested} was not found."
        return fallback, ""

    def _load_edition(self, edition: str) -> dict[str, str]:
        if edition not in self._cache:
            canon_path = self.root / edition / "verses.json"
            logger.info("Loading local Bible preview canon: %s", canon_path)
            with canon_path.open("r", encoding="utf-8") as fh:
                self._cache[edition] = json.load(fh)
        return self._cache[edition]

    def _parse_reference(
        self, reference: str
    ) -> Optional[tuple[str, int, Optional[int], Optional[int]]]:
        match = _REFERENCE_RE.match(reference.strip())
        if not match:
            return None

        book = match.group("book").strip()
        chapter = int(match.group("chapter"))
        verse_start = match.group("start")
        verse_end = match.group("end")
        return (
            book,
            chapter,
            int(verse_start) if verse_start is not None else None,
            int(verse_end) if verse_end is not None else None,
        )

    def _preview_range(
        self,
        book: str,
        chapter: int,
        verse_start: int,
        verse_end: int,
        verses: dict[str, str],
        edition: str,
        reference: str,
        edition_note: str,
    ) -> BiblePreview:
        lines: list[str] = []
        missing: list[int] = []

        for verse_number in range(verse_start, verse_end + 1):
            key = f"{book} {chapter}:{verse_number}"
            text = verses.get(key)
            if not text:
                missing.append(verse_number)
                continue
            lines.append(f"{verse_number}  {self._clean_text(text)}")

        if not lines:
            return BiblePreview(
                edition=edition,
                reference=reference,
                body=f"No local text was found for {reference} in {edition}.",
                found=False,
                note=edition_note or "Preview unavailable",
            )

        note_parts = [edition_note] if edition_note else []
        if missing:
            note_parts.append(
                "Missing verse text for " + ", ".join(str(number) for number in missing)
            )
        return BiblePreview(
            edition=edition,
            reference=reference,
            body="\n\n".join(lines),
            found=True,
            note=" ".join(part for part in note_parts if part).strip(),
        )

    def _preview_chapter(
        self,
        book: str,
        chapter: int,
        verses: dict[str, str],
        edition: str,
        reference: str,
        edition_note: str,
    ) -> BiblePreview:
        chapter_verses: list[tuple[int, str]] = []
        for key, text in verses.items():
            match = _CHAPTER_KEY_RE.match(key)
            if not match:
                continue
            if match.group("book") != book or int(match.group("chapter")) != chapter:
                continue
            chapter_verses.append((int(match.group("verse")), text))

        if not chapter_verses:
            return BiblePreview(
                edition=edition,
                reference=reference,
                body=f"No local text was found for {reference} in {edition}.",
                found=False,
                note=edition_note or "Preview unavailable",
            )

        chapter_verses.sort(key=lambda item: item[0])
        preview_limit = 10
        lines = [
            f"{verse_number}  {self._clean_text(text)}"
            for verse_number, text in chapter_verses[:preview_limit]
        ]
        note_parts = [edition_note] if edition_note else []
        if len(chapter_verses) > preview_limit:
            note_parts.append(f"Chapter preview limited to the first {preview_limit} verses.")

        return BiblePreview(
            edition=edition,
            reference=reference,
            body="\n\n".join(lines),
            found=True,
            note=" ".join(part for part in note_parts if part).strip(),
        )

    def _clean_text(self, text: str) -> str:
        return text.lstrip("# ").strip()
