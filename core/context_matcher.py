"""
core/context_matcher.py
Contextual Bible passage matching for sermon text without explicit verse mentions.
"""

from __future__ import annotations

import json
import logging
import math
import re
import threading
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from core.bible_detector import VerseMatch
from core.bible_preview import BiblePreviewLibrary

logger = logging.getLogger(__name__)

_REFERENCE_RE = re.compile(
    r"^(?P<book>.+?)\s+(?P<chapter>\d+):(?P<start>\d+)(?:-(?P<end>\d+))?$"
)
_VERSE_KEY_RE = re.compile(r"^(?P<book>.+?)\s+(?P<chapter>\d+):(?P<verse>\d+)$")
_TOKEN_RE = re.compile(r"[a-zA-Z']+")
_STOPWORDS = {
    "the", "and", "that", "with", "from", "this", "there", "their", "them",
    "they", "were", "have", "your", "about", "into", "when", "what", "which",
    "would", "could", "should", "shall", "unto", "than", "then", "because",
    "while", "where", "here", "been", "being", "also", "only", "very", "much",
    "more", "most", "some", "such", "each", "many", "over", "under", "into",
    "upon", "through", "them", "ours", "ourselves", "yourself", "yourselves",
    "his", "hers", "theirs", "our", "ours", "your", "yours", "its", "for",
    "are", "was", "were", "but", "not", "you", "all", "any", "can", "had",
    "has", "her", "him", "his", "how", "let", "may", "off", "one", "out",
    "she", "too", "use", "who", "why", "will", "said", "says", "say",
}


def _try_sentence_transformers():
    try:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer
    except Exception as exc:
        logger.debug("sentence-transformers unavailable: %s", exc)
        return None


@dataclass(frozen=True)
class PassageSuggestion:
    reference: str
    text: str
    score: float
    lexical_score: float
    semantic_score: Optional[float]
    method: str
    verse_match: VerseMatch

    @property
    def score_percent(self) -> int:
        return int(round(self.score * 100))


@dataclass(frozen=True)
class _PassageCandidate:
    reference: str
    text: str
    verse_match: VerseMatch


class ContextPassageMatcher:
    WINDOW_SIZES = (1, 3)
    MIN_QUERY_TOKENS = 4
    TOP_K = 12
    MIN_SCORE = 0.18
    MIN_MARGIN = 0.015

    def __init__(
        self,
        translation: str = "KJV",
        *,
        semantic_model_name: str = "all-MiniLM-L6-v2",
    ):
        self.translation = translation
        self.semantic_model_name = semantic_model_name
        self._lock = threading.Lock()
        self._ready = False
        self._preparing = False
        self._prepare_error = ""
        self._candidates: list[_PassageCandidate] = []
        self._idf: dict[str, float] = {}
        self._inverted_index: dict[str, list[tuple[int, float]]] = {}
        self._doc_norms: list[float] = []
        self._sentence_model = None
        self._sentence_transformer_cls = _try_sentence_transformers()
        self._resolved_translation = translation

    @property
    def is_ready(self) -> bool:
        return self._ready

    @property
    def backend_name(self) -> str:
        if self._sentence_transformer_cls:
            return "keyword+semantic"
        return "keyword"

    def warm_async(self):
        with self._lock:
            if self._ready or self._preparing:
                return
            self._preparing = True

        worker = threading.Thread(target=self._prepare_async_worker, daemon=True)
        worker.start()

    def suggest(
        self,
        context_text: str,
        *,
        exclude_references: Optional[set[str]] = None,
    ) -> Optional[PassageSuggestion]:
        if not self._ready:
            self.warm_async()
            return None

        exclude_references = exclude_references or set()
        query_tokens = self._tokenize(context_text)
        if len(query_tokens) < self.MIN_QUERY_TOKENS:
            return None

        ranked = self._keyword_rank(context_text, exclude_references, self.TOP_K)
        if not ranked:
            return None

        if self._sentence_transformer_cls:
            ranked = self._semantic_rerank(context_text, ranked)

        best_score, best_candidate, lexical_score, semantic_score = ranked[0]
        if best_score < self.MIN_SCORE:
            return None
        if len(ranked) > 1 and best_score < ranked[1][0] + self.MIN_MARGIN:
            return None

        return PassageSuggestion(
            reference=best_candidate.reference,
            text=best_candidate.text,
            score=max(0.0, min(best_score, 0.99)),
            lexical_score=lexical_score,
            semantic_score=semantic_score,
            method="semantic" if semantic_score is not None else "keyword",
            verse_match=best_candidate.verse_match,
        )

    def _prepare_async_worker(self):
        try:
            self._prepare()
        except Exception as exc:
            logger.exception("Failed to prepare context passage matcher")
            self._prepare_error = str(exc)
        finally:
            with self._lock:
                self._preparing = False

    def _prepare(self):
        logger.info("Preparing contextual passage matcher for %s", self.translation)
        candidates = self._build_candidates()
        idf, inverted_index, doc_norms = self._build_keyword_index(candidates)

        with self._lock:
            self._candidates = candidates
            self._idf = idf
            self._inverted_index = inverted_index
            self._doc_norms = doc_norms
            self._ready = True

        logger.info(
            "Context matcher ready with %d passage candidates (%s)",
            len(candidates),
            self.backend_name,
        )

    def _build_candidates(self) -> list[_PassageCandidate]:
        library = BiblePreviewLibrary()
        editions = library.available_editions()
        if not editions:
            logger.warning("No canon editions available for context matching")
            return []

        edition = self._resolve_translation(editions)
        verses_path = Path(library.root) / edition / "verses.json"
        verses = json.loads(verses_path.read_text(encoding="utf-8"))

        chapters: dict[tuple[str, int], list[tuple[int, str]]] = defaultdict(list)
        for key, text in verses.items():
            match = _VERSE_KEY_RE.match(key)
            if not match:
                continue
            book = match.group("book")
            chapter = int(match.group("chapter"))
            verse = int(match.group("verse"))
            chapters[(book, chapter)].append((verse, self._clean_text(text)))

        candidates: list[_PassageCandidate] = []
        for (book, chapter), chapter_verses in chapters.items():
            chapter_verses.sort(key=lambda item: item[0])
            for window_size in self.WINDOW_SIZES:
                if len(chapter_verses) < window_size:
                    continue
                for idx in range(0, len(chapter_verses) - window_size + 1):
                    window = chapter_verses[idx : idx + window_size]
                    first_verse = window[0][0]
                    last_verse = window[-1][0]
                    reference = f"{book} {chapter}:{first_verse}"
                    if first_verse != last_verse:
                        reference += f"-{last_verse}"
                    candidate_text = " ".join(text for _, text in window).strip()
                    candidates.append(
                        _PassageCandidate(
                            reference=reference,
                            text=candidate_text,
                            verse_match=VerseMatch(
                                raw_text=candidate_text[:200],
                                book=book,
                                chapter=chapter,
                                verse_start=first_verse,
                                verse_end=last_verse if last_verse != first_verse else None,
                                confidence=0.0,
                            ),
                        )
                    )
        return candidates

    def _build_keyword_index(
        self, candidates: list[_PassageCandidate]
    ) -> tuple[dict[str, float], dict[str, list[tuple[int, float]]], list[float]]:
        document_tokens: list[Counter[str]] = []
        document_frequency: Counter[str] = Counter()

        for candidate in candidates:
            counts = Counter(self._tokenize(f"{candidate.reference} {candidate.text}"))
            document_tokens.append(counts)
            document_frequency.update(set(counts))

        total_docs = len(candidates) or 1
        idf = {
            token: math.log((total_docs + 1) / (frequency + 1)) + 1.0
            for token, frequency in document_frequency.items()
        }

        inverted_index: dict[str, list[tuple[int, float]]] = defaultdict(list)
        doc_norms: list[float] = []

        for doc_id, counts in enumerate(document_tokens):
            squared_sum = 0.0
            for token, term_frequency in counts.items():
                weight = (1.0 + math.log(term_frequency)) * idf[token]
                inverted_index[token].append((doc_id, weight))
                squared_sum += weight * weight
            doc_norms.append(math.sqrt(squared_sum) or 1.0)

        return idf, dict(inverted_index), doc_norms

    def _keyword_rank(
        self,
        context_text: str,
        exclude_references: set[str],
        top_k: int,
    ) -> list[tuple[float, _PassageCandidate, float, Optional[float]]]:
        query_counts = Counter(self._tokenize(context_text))
        if not query_counts:
            return []

        scores: dict[int, float] = defaultdict(float)
        query_squared_sum = 0.0

        for token, term_frequency in query_counts.items():
            query_weight = (1.0 + math.log(term_frequency)) * self._idf.get(token, 0.0)
            if query_weight <= 0:
                continue
            query_squared_sum += query_weight * query_weight
            for doc_id, doc_weight in self._inverted_index.get(token, []):
                scores[doc_id] += query_weight * doc_weight

        query_norm = math.sqrt(query_squared_sum) or 1.0
        ranked: list[tuple[float, _PassageCandidate, float, Optional[float]]] = []

        for doc_id, dot_product in scores.items():
            candidate = self._candidates[doc_id]
            if candidate.reference in exclude_references:
                continue
            lexical_score = dot_product / (query_norm * self._doc_norms[doc_id])
            ranked.append((lexical_score, candidate, lexical_score, None))

        ranked.sort(key=lambda item: item[0], reverse=True)
        return ranked[:top_k]

    def _semantic_rerank(
        self,
        context_text: str,
        ranked: list[tuple[float, _PassageCandidate, float, Optional[float]]],
    ) -> list[tuple[float, _PassageCandidate, float, Optional[float]]]:
        model = self._get_sentence_model()
        if not model or not ranked:
            return ranked

        payload = [context_text]
        payload.extend(f"{candidate.reference}. {candidate.text}" for _, candidate, _, _ in ranked)

        try:
            embeddings = model.encode(
                payload,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
        except Exception as exc:
            logger.warning("Semantic rerank failed; using keyword-only matching: %s", exc)
            return ranked

        query_embedding = embeddings[0]
        reranked: list[tuple[float, _PassageCandidate, float, Optional[float]]] = []
        for idx, (keyword_score, candidate, lexical_score, _) in enumerate(ranked, start=1):
            semantic_score = float(np.dot(query_embedding, embeddings[idx]))
            combined_score = (0.65 * semantic_score) + (0.35 * lexical_score)
            reranked.append((combined_score, candidate, lexical_score, semantic_score))

        reranked.sort(key=lambda item: item[0], reverse=True)
        return reranked

    def _get_sentence_model(self):
        if not self._sentence_transformer_cls:
            return None
        if self._sentence_model is not None:
            return self._sentence_model

        try:
            logger.info("Loading sentence-transformers model: %s", self.semantic_model_name)
            self._sentence_model = self._sentence_transformer_cls(self.semantic_model_name)
        except Exception as exc:
            logger.warning("Could not load sentence-transformers model: %s", exc)
            self._sentence_model = None
            self._sentence_transformer_cls = None
        return self._sentence_model

    def _resolve_translation(self, editions: list[str]) -> str:
        requested = self.translation.strip()
        if requested:
            for edition in editions:
                if edition.lower() == requested.lower():
                    self._resolved_translation = edition
                    return edition
        self._resolved_translation = editions[0]
        return self._resolved_translation

    def _tokenize(self, text: str) -> list[str]:
        tokens = []
        for token in _TOKEN_RE.findall(text.lower()):
            if len(token) < 3 or token in _STOPWORDS:
                continue
            tokens.append(token)
        return tokens

    def _clean_text(self, text: str) -> str:
        return text.lstrip("# ").strip()
