"""Small TF-IDF search over data/kb (gov.uk, FCA, Citizens Advice snapshots).

A stand-in for the RAG /ask endpoint (Agent B). The voice tool always returns sources.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

KB = Path(__file__).resolve().parents[2] / "data" / "kb"
STOP = set("""a an and are as at be by can do does for from has have how i if in is it its my of on or so that the
this to was what when where which who will with you your me we our they them their than then there about into
not no yes any all more most much many should would could""".split())


@dataclass
class Chunk:
    title: str
    url: str
    heading: str
    text: str
    tokens: Counter


def _tok(s: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9£%]+", s.lower()) if w not in STOP and len(w) > 1]


def _parse(path: Path) -> list[Chunk]:
    raw = path.read_text()
    meta = dict(re.findall(r'^(\w+): "?(.*?)"?$', raw.split("---", 2)[1], re.M)) if raw.startswith("---") else {}
    body = raw.split("---", 2)[2] if raw.startswith("---") else raw
    chunks, heading, buf = [], meta.get("title", path.stem), []

    def flush():
        text = " ".join(buf).strip()
        if len(text) > 80:
            chunks.append(Chunk(meta.get("title", path.stem), meta.get("url", ""), heading, text,
                                Counter(_tok(heading + " " + meta.get("title", "") + " " + text))))

    for line in body.splitlines():
        if line.startswith("#"):
            flush()
            heading, buf = line.lstrip("# ").strip(), []
        elif line.strip():
            buf.append(line.strip().lstrip("- "))
            if sum(len(b) for b in buf) > 900:
                flush()
                buf = []
    flush()
    return chunks


@lru_cache(maxsize=1)
def _index() -> tuple[list[Chunk], dict[str, float]]:
    chunks = [c for p in sorted(KB.glob("*/*.md")) for c in _parse(p)]
    df = Counter(t for c in chunks for t in set(c.tokens))
    n = max(len(chunks), 1)
    idf = {t: math.log(1 + n / d) for t, d in df.items()}
    return chunks, idf


def search(query: str, k: int = 3) -> list[dict]:
    chunks, idf = _index()
    q = _tok(query)
    if not q or not chunks:
        return []
    scored = []
    for c in chunks:
        length = sum(c.tokens.values()) or 1
        s = sum(idf.get(t, 0) * (c.tokens[t] / (c.tokens[t] + 1.2 * (0.25 + 0.75 * length / 120))) for t in q)
        if s > 0:
            scored.append((s, c))
    scored.sort(key=lambda x: -x[0])
    out, seen = [], set()
    for s, c in scored:
        key = (c.title, c.heading)  # gov.uk guide parts share a title, so dedupe on title + section
        if key in seen:
            continue
        seen.add(key)
        out.append({"title": c.title, "section": c.heading, "url": c.url, "text": c.text[:700], "score": round(s, 2)})
        if len(out) == k:
            break
    return out
