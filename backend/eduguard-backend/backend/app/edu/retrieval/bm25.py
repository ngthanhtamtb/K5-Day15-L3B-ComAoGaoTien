"""Dependency-free BM25 over document chunks.

RAGslides puts the whole document into the prompt. That works for short lessons, but for
grounding (the Eval panel must show *which* passage supports an answer) we need retrieval
with stable chunk ids. Swap this class for a vector store later; the interface is tiny.
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from typing import List, Optional, Tuple

from app.edu.docparse.models import Chunk

_TOKEN = re.compile(r"\w+", re.UNICODE)


def tokenize(text: str) -> List[str]:
    text = unicodedata.normalize("NFC", text.lower())
    toks = _TOKEN.findall(text)
    # Vietnamese meaning lives in syllable pairs ("chiến dịch"), so add bigrams.
    return toks + [f"{a}_{b}" for a, b in zip(toks, toks[1:])]


class ChunkRetriever:
    def __init__(self, chunks: List[Chunk], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1, self.b = k1, b
        self.docs = [Counter(tokenize(" ".join(c.heading_path) + " " + c.text)) for c in chunks]
        self.lens = [sum(d.values()) for d in self.docs]
        self.avg = (sum(self.lens) / len(self.lens)) if self.lens else 0
        df: Counter = Counter()
        for d in self.docs:
            df.update(d.keys())
        n = len(chunks)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, k: int = 4) -> List[Tuple[Chunk, float]]:
        q = tokenize(query)
        scores = []
        for i, d in enumerate(self.docs):
            s = 0.0
            for t in q:
                if t not in d:
                    continue
                tf = d[t]
                s += self.idf[t] * tf * (self.k1 + 1) / (
                    tf + self.k1 * (1 - self.b + self.b * self.lens[i] / (self.avg or 1)))
            if s > 0:
                scores.append((self.chunks[i], s))
        scores.sort(key=lambda x: -x[1])
        return scores[:k]

    def get(self, chunk_id: str) -> Optional[Chunk]:
        return next((c for c in self.chunks if c.id == chunk_id), None)
