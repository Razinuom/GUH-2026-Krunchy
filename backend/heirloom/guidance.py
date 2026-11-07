"""/ask, plus the shared rules and sources used by Claim Check (claimcheck.py).

No API keys: red flags are the FCA ScamSmart warning signs, and every answer cites the GOV.UK,
FCA or Citizens Advice page it came from (via backend.voice.kb_search). Guidance, not advice.
"""
from __future__ import annotations

import re

from backend.voice import kb_search

DISCLAIMER = "Guidance, not regulated financial advice. Always check a firm on the FCA Register before acting."

SRC = {
    "scamsmart": {"title": "FCA ScamSmart: how to avoid investment scams",
                  "url": "https://www.fca.org.uk/scamsmart/how-avoid-investment-scams"},
    "register": {"title": "FCA Financial Services Register", "url": "https://register.fca.org.uk/"},
    "crypto": {"title": "FCA: cryptoassets", "url": "https://www.fca.org.uk/consumers/cryptoassets"},
    "recovery": {"title": "FCA: recovery room scams", "url": "https://www.fca.org.uk/consumers/recovery-room-scams"},
    "loanfee": {"title": "FCA: loan fee fraud", "url": "https://www.fca.org.uk/consumers/loan-fee-fraud"},
    "pension": {"title": "FCA: pension scams", "url": "https://www.fca.org.uk/consumers/pension-scams"},
    "ca": {"title": "Citizens Advice: check if something might be a scam",
           "url": "https://www.citizensadvice.org.uk/consumer/scams/check-if-something-might-be-a-scam/"},
    "lisa": {"title": "GOV.UK: Lifetime ISA", "url": "https://www.gov.uk/lifetime-isa"},
    "isa": {"title": "GOV.UK: Individual Savings Accounts", "url": "https://www.gov.uk/individual-savings-accounts"},
    "iht": {"title": "GOV.UK: gifts and Inheritance Tax", "url": "https://www.gov.uk/inheritance-tax/gifts"},
}

RED_FLAGS = [
    (r"guarantee|guaranteed|can'?t lose|no risk|risk[- ]free", "Promises guaranteed returns or no risk", "scamsmart"),
    (r"\b\d+\s?x\b|(double|triple) (your|my)|\d{3,}\s?%", "Returns far above anything a regulated product offers",
     "scamsmart"),
    (r"act now|today only|limited (spots|time|places)|before it'?s too late|last chance",
     "Pressure to act quickly", "ca"),
    (r"\b(dm|whatsapp|telegram|message me|link in bio)\b", "Moves the conversation to private messages", "ca"),
    (r"crypto|bitcoin|\btoken\b|\bcoin\b", "Cryptoassets are largely unregulated in the UK", "crypto"),
    (r"recover (your|lost)|get your money back", "Offers to recover money already lost", "recovery"),
    (r"upfront fee|pay a fee to (get|release)|loan.*\bfee\b", "Asks for a fee before a loan is paid", "loanfee"),
    (r"pension (release|unlock|liberation)|access your pension early", "Offers early access to a pension",
     "pension"),
]

ADVICE_PATTERNS = r"which (stock|share|fund|crypto|coin)|what should i (buy|invest)|best (stock|fund|investment)|" \
                  r"should i (buy|sell|invest)|tip(s)? for (stocks|shares)"


def _dedupe(sources: list[dict]) -> list[dict]:
    seen, out = set(), []
    for s in sources:
        if s["url"] not in seen:
            seen.add(s["url"])
            out.append(s)
    return out


def _sentences(text: str, n: int) -> str:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(parts[:n])


def ask(question: str, lang: str = "en") -> dict:
    """Extractive answer from the official-guidance snapshot. Refuses personal investment picks."""
    if re.search(ADVICE_PATTERNS, question, re.I):
        return {"answer": ("I can't recommend specific investments. That needs a regulated financial adviser. "
                           "MoneyHelper (0800 138 7777) explains the options for free and can help you find one."),
                "sources": [{"title": "MoneyHelper", "url": "https://www.moneyhelper.org.uk"},
                            SRC["register"]],
                "refused": True, "lang": "en", "disclaimer": DISCLAIMER}
    hits = kb_search.search(question, 3)
    if not hits:
        return {"answer": ("I couldn't find official guidance on that. MoneyHelper (0800 138 7777) can help for "
                           "free."), "sources": [], "refused": False, "lang": "en", "disclaimer": DISCLAIMER}
    top = hits[0]
    answer = f"{_sentences(top['text'], 3)} (Source: {top['title']})"
    return {"answer": answer, "sources": _dedupe([{"title": h["title"], "url": h["url"]} for h in hits]),
            "refused": False, "lang": "en", "disclaimer": DISCLAIMER}
