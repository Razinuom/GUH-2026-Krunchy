"""Voice coach backend for the ElevenLabs agent.

  GET  /voice/status                   is the voice layer configured? (never returns secrets)
  GET  /voice/session?member_id=...    signed URL + dynamic variables for the browser to start a conversation
  GET  /voice/events?family_id=...     Server-Sent Events: the dashboard updates (in English) as the agent works
  POST /voice/tools/<tool>             webhook tools called by the ElevenLabs agent (see agent_spec.TOOLS)
  POST /voice/webhooks/post-call       ElevenLabs post-call webhook (HMAC verified), logs the transcript
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from backend.heirloom import service, synth
from backend.heirloom.personas import personas

from . import kb_search
from .agent_spec import TOOL_SECRET_HEADER
from .config import settings
from .events import bus

router = APIRouter(prefix="/voice", tags=["voice"])
LOG_DIR = Path(__file__).resolve().parents[2] / "data" / "voice"
LANGUAGE_NAMES = {"en": "English", "pl": "Polish", "ms": "Malay", "zh": "Mandarin Chinese", "uk": "Ukrainian", "ro": "Romanian", "pa": "Punjabi",
                  "ur": "Urdu", "ar": "Arabic", "es": "Spanish", "pt": "Portuguese", "fr": "French"}
SIGNATURE_TOLERANCE_SECS = 30 * 60

HELP = {
    "moneyhelper": {"name": "MoneyHelper", "phone": "0800 138 7777", "url": "https://www.moneyhelper.org.uk",
                    "what": "Free, impartial money and pensions guidance, backed by government"},
    "stepchange": {"name": "StepChange Debt Charity", "phone": "0800 138 1111", "url": "https://www.stepchange.org",
                   "what": "Free debt advice and debt solutions"},
    "national_debtline": {"name": "National Debtline", "phone": "0808 808 4000", "url": "https://nationaldebtline.org",
                          "what": "Free debt advice by phone and online"},
    "stop_scams": {"name": "Stop Scams UK", "phone": "159",
                   "url": "https://stopscamsuk.org.uk/159", "what": "Call 159 to reach your bank safely if you "
                                                               "think you are being scammed"},
    "action_fraud": {"name": "Action Fraud", "phone": "0300 123 2040", "url": "https://www.actionfraud.police.uk",
                     "what": "Report fraud and cybercrime"},
    "fca_register": {"name": "FCA Financial Services Register", "phone": "0800 111 6768",
                     "url": "https://register.fca.org.uk", "what": "Check a firm or adviser is authorised"},
    "samaritans": {"name": "Samaritans", "phone": "116 123", "url": "https://www.samaritans.org",
                   "what": "Free, 24/7 emotional support"},
    "citizens_advice": {"name": "Citizens Advice", "phone": "0800 144 8848",
                        "url": "https://www.citizensadvice.org.uk",
                        "what": "Help with benefits, bills, scams and consumer problems"},
}
HELP_BY_REASON = {
    "debt": ["stepchange", "national_debtline", "moneyhelper"],
    "scam": ["stop_scams", "action_fraud", "fca_register"],
    "advice": ["moneyhelper", "fca_register"],
    "distress": ["samaritans", "stepchange", "moneyhelper"],
    "other": ["moneyhelper", "stepchange", "citizens_advice"],
}


# ------------------------------------------------------------------ helpers
def require_tool_secret(x_heirloom_tool_secret: str | None = Header(None, alias=TOOL_SECRET_HEADER)) -> None:
    secret = settings().tool_secret
    if secret and not hmac.compare_digest(x_heirloom_tool_secret or "", secret):
        raise HTTPException(401, "Invalid tool secret")


def _member(member_id: str):
    p = personas().get((member_id or "").strip().lower())
    if not p:
        raise HTTPException(404, f"Unknown member_id '{member_id}'")
    return p


def _gbp(x: float) -> str:
    return f"-£{abs(x):,.0f}" if x < 0 else f"£{x:,.0f}"


def _odds(p: float) -> str:
    if p <= 0.005:
        return "very unlikely (under 1 percent)"
    if p >= 0.95:
        return "almost certain"
    n = round(1 / p)
    return f"about 1 in {n}" if n >= 2 else f"about {round(p * 100)} percent"


def _nice_date(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d:%A} {d.day} {d:%B}"


def _log(name: str, record: dict) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with (LOG_DIR / name).open("a") as f:
        f.write(json.dumps(record, default=str) + "\n")


def _lang(code: str | None) -> dict:
    c = (code or "en").lower()[:2]
    return {"code": c, "name": LANGUAGE_NAMES.get(c, c)}


# ------------------------------------------------------------------ status / session / events
@router.get("/test", include_in_schema=False)
def voice_test_page() -> FileResponse:
    """Browser page to talk to the agent by voice and watch the dashboard events: /voice/test"""
    return FileResponse(Path(__file__).with_name("static") / "voice_test.html")


@router.get("/status")
def status() -> dict:
    s = settings()
    return {"api_key_set": bool(s.api_key), "agent_id_set": bool(s.agent_id), "configured": s.configured,
            "tool_secret_set": bool(s.tool_secret), "webhook_secret_set": bool(s.webhook_secret),
            "public_base_url": s.public_base_url or None}


@router.get("/session")
async def session(member_id: str = "halina") -> dict:
    """Everything the browser needs to start a conversation without seeing the API key.

    Frontend (@elevenlabs/react or @elevenlabs/client):
        const s = await fetch(`/voice/session?member_id=halina`).then(r => r.json())
        conversation.startSession({ signedUrl: s.signed_url, dynamicVariables: s.dynamic_variables })
    """
    p = _member(member_id)
    s = settings()
    if not s.configured:
        raise HTTPException(503, "Voice not configured: set ELEVENLABS_API_KEY and ELEVENLABS_AGENT_ID in .env "
                                 "(run `python -m backend.voice.provision` to create the agent).")
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{s.api_base}/v1/convai/conversation/get-signed-url",
                             params={"agent_id": s.agent_id}, headers={"xi-api-key": s.api_key})
    if r.status_code != 200:
        raise HTTPException(502, f"ElevenLabs signed URL request failed ({r.status_code})")
    bus.publish("session_started", p.family, {"member_id": p.id, "member_name": p.name})
    return {"signed_url": r.json()["signed_url"], "agent_id": s.agent_id,
            "dynamic_variables": {"member_id": p.id, "member_name": p.name.split()[0], "family_id": p.family}}


@router.get("/events")
async def events(family_id: str | None = None) -> StreamingResponse:
    return StreamingResponse(bus.stream(family_id), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.get("/events/recent")
def recent_events(family_id: str | None = None) -> list[dict]:
    return [e for e in bus.recent if family_id is None or e["family_id"] in (None, family_id)]


# ------------------------------------------------------------------ tools
class ForecastToolIn(BaseModel):
    member_id: str
    language: str = "en"
    question: str = ""


class WhatIfIn(BaseModel):
    member_id: str
    amount: float = Field(..., gt=0, le=1_000_000)
    days_from_now: int = 0
    description: str = "Planned payment"
    language: str = "en"


class RulesIn(BaseModel):
    query: str = Field(..., min_length=2)
    language: str = "en"
    member_id: str | None = None


class HandoffIn(BaseModel):
    member_id: str
    reason: Literal["debt", "scam", "advice", "distress", "other"] | str = "other"
    summary: str = ""
    language: str = "en"


def _forecast_digest(r: dict) -> dict:
    low = r["lowest_point"]
    return {
        "current_balance": round(r["start_balance"]),
        "risk_level": r["risk_band"],
        "chance_overdrawn_next_90_days_percent": round(r["overdraft_probability"] * 100),
        "chance_overdrawn_in_words": _odds(r["overdraft_probability"]),
        "chance_overdrawn_next_30_days_percent": round(r["overdraft_probability_by_horizon"].get("30", 0) * 100),
        "lowest_point": {"date": low["date"], "date_spoken": _nice_date(low["date"]),
                         "expected_balance": low["p50"], "bad_case_balance": low["p10"]},
        "main_reasons": [{"reason": x["feature"], "detail": x["detail"],
                          "share_of_risk_percent": round(x["impact"] * 100)} for x in r["reasons"]],
    }


@router.post("/tools/get_cash_forecast", dependencies=[Depends(require_tool_secret)])
async def tool_get_cash_forecast(body: ForecastToolIn) -> dict:
    p = _member(body.member_id)
    r = await run_in_threadpool(service.forecast_now, p.id)
    d = _forecast_digest(r)
    first = p.name.split()[0]
    reasons = "; ".join(f"{x['reason']} ({x['detail']})" for x in d["main_reasons"][:3]) or "nothing stands out"
    odds = d["chance_overdrawn_in_words"]
    if "percent" not in odds and "certain" not in odds:
        odds += f" ({d['chance_overdrawn_next_90_days_percent']}%)"
    summary = (f"{first} has {_gbp(d['current_balance'])} now. Over the next 90 days the balance is expected to be "
               f"lowest around {d['lowest_point']['date_spoken']}, at about {_gbp(d['lowest_point']['expected_balance'])} "
               f"(in a bad case {_gbp(d['lowest_point']['bad_case_balance'])}). The chance of going overdrawn is "
               f"{odds}. Main reasons: {reasons}.")
    bus.publish("forecast", p.family, {"member_id": p.id, "member_name": p.name, "question_en": body.question,
                                       "spoken_language": _lang(body.language), "summary_en": summary,
                                       "forecast": r})
    return {"member": p.name, **d,
            "next_payments": [{"date_spoken": _nice_date(u["date"]), "what": u["merchant"].title(),
                               "amount": round(u["amount"])} for u in r["upcoming"][:4]],
            "summary_en": summary,
            "reply_instructions": "Answer in the person's language. Guidance only, not financial advice."}


@router.post("/tools/what_if_payment", dependencies=[Depends(require_tool_secret)])
async def tool_what_if_payment(body: WhatIfIn) -> dict:
    p = _member(body.member_id)
    days = max(0, min(body.days_from_now, 89))
    as_of = synth.default_as_of()
    when = as_of + timedelta(days=days)
    change = {"kind": "one_off", "date": when, "amount": -round(body.amount, 2), "feature": body.description or
              "Planned payment", "detail": f"{_gbp(body.amount)} on {_nice_date(when.isoformat())}"}
    before = await run_in_threadpool(service.forecast_now, p.id)
    after = await run_in_threadpool(service.forecast_what_if, p.id, [change])
    pb, pa = before["overdraft_probability"], after["overdraft_probability"]
    low_a = after["lowest_point"]
    verdict = ("affordable: the balance is expected to stay comfortably above zero" if pa < 0.10 and low_a["p10"] > 0
               else "tight: possible, but the balance gets close to zero" if pa < 0.30
               else "risky: this would likely lead to going overdrawn")
    summary = (f"Paying {_gbp(body.amount)} ({change['feature']}) on {_nice_date(when.isoformat())} would change the "
               f"chance of going overdrawn in the next 90 days from {round(pb * 100)}% to {round(pa * 100)}%. The lowest "
               f"point would be about {_gbp(low_a['p50'])} around {_nice_date(low_a['date'])}. Verdict: {verdict}.")
    bus.publish("what_if", p.family, {"member_id": p.id, "member_name": p.name, "spoken_language": _lang(body.language),
                                      "payment": {"amount": body.amount, "date": when.isoformat(),
                                                  "description": change["feature"]},
                                      "before": {"overdraft_probability": pb, "lowest_point": before["lowest_point"]},
                                      "after_forecast": after, "summary_en": summary})
    return {"member": p.name, "payment_amount": round(body.amount), "payment_date_spoken": _nice_date(when.isoformat()),
            "chance_overdrawn_before_percent": round(pb * 100), "chance_overdrawn_after_percent": round(pa * 100),
            "lowest_point_after": {"date_spoken": _nice_date(low_a["date"]), "expected_balance": low_a["p50"],
                                   "bad_case_balance": low_a["p10"]},
            "verdict": verdict, "summary_en": summary,
            "scope": "Current account only. Savings accounts and ISAs are not included.",
            "reply_instructions": "Answer in the person's language. This is a scenario, not advice. Say clearly that "
                                  "this only looks at the current account, not savings. If the verdict is risky, "
                                  "gently suggest a smaller amount, a later date, or paying it from savings."}


@router.post("/tools/lookup_money_rules", dependencies=[Depends(require_tool_secret)])
async def tool_lookup_money_rules(body: RulesIn) -> dict:
    hits = await run_in_threadpool(kb_search.search, body.query, 3)
    fam = personas()[body.member_id.lower()].family if body.member_id and body.member_id.lower() in personas() else None
    bus.publish("rules_lookup", fam, {"query_en": body.query, "spoken_language": _lang(body.language),
                                      "sources": [{"title": h["title"], "section": h["section"], "url": h["url"]}
                                                  for h in hits]})
    if not hits:
        return {"found": False, "passages": [],
                "reply_instructions": "Say you could not find official guidance on this and offer MoneyHelper "
                                      "(0800 138 7777)."}
    return {"found": True,
            "passages": [{"source": h["title"], "section": h["section"], "url": h["url"], "text": h["text"]}
                         for h in hits],
            "reply_instructions": "Explain simply in the person's language using only these passages, and name the "
                                  "source (e.g. GOV.UK). Do not give personal recommendations."}


@router.post("/tools/talk_to_a_person", dependencies=[Depends(require_tool_secret)])
async def tool_talk_to_a_person(body: HandoffIn) -> dict:
    p = _member(body.member_id)
    reason = body.reason if body.reason in HELP_BY_REASON else "other"
    contacts = [HELP[k] for k in HELP_BY_REASON[reason]]
    record = {"ts": datetime.now(timezone.utc).isoformat(), "member_id": p.id, "family_id": p.family,
              "reason": reason, "summary": body.summary, "language": _lang(body.language)["code"]}
    _log("escalations.jsonl", record)
    bus.publish("escalation", p.family, {**record, "member_name": p.name, "contacts": contacts})
    return {"handoff_logged": True, "reason": reason, "contacts": contacts,
            "reply_instructions": "Calmly share the first one or two contacts (name and phone number, said slowly). "
                                  "Say they are free and confidential. The details are also shown on the screen."
                                  + (" If they are in immediate danger, tell them to call 999." if reason == "distress"
                                     else "")
                                  + (" Tell them not to send any money or share codes until they have checked."
                                     if reason == "scam" else "")}


# ------------------------------------------------------------------ post-call webhook
def verify_elevenlabs_signature(raw: bytes, header: str | None, secret: str, now: float | None = None) -> bool:
    """ElevenLabs-Signature: t=<unix>,v0=<hex hmac_sha256(secret, f"{t}.{body}")>"""
    if not header:
        return False
    parts = dict(kv.split("=", 1) for kv in header.split(",") if "=" in kv)
    t, sig = parts.get("t"), parts.get("v0")
    if not t or not sig or not t.isdigit():
        return False
    if abs((now or time.time()) - int(t)) > SIGNATURE_TOLERANCE_SECS:
        return False
    expected = hmac.new(secret.encode(), f"{t}.{raw.decode()}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig)


@router.post("/webhooks/post-call")
async def post_call(request: Request, elevenlabs_signature: str | None = Header(None)) -> dict:
    raw = await request.body()
    secret = settings().webhook_secret
    if secret and not verify_elevenlabs_signature(raw, elevenlabs_signature, secret):
        raise HTTPException(401, "Invalid signature")
    payload = json.loads(raw or b"{}")
    data = payload.get("data", {})
    dyn = (data.get("conversation_initiation_client_data") or {}).get("dynamic_variables") or {}
    record = {"ts": datetime.now(timezone.utc).isoformat(), "type": payload.get("type"),
              "conversation_id": data.get("conversation_id"), "member_id": dyn.get("member_id"),
              "summary": (data.get("analysis") or {}).get("transcript_summary"),
              "turns": len(data.get("transcript") or [])}
    _log("conversations.jsonl", {**record, "transcript": data.get("transcript")})
    bus.publish("call_ended", dyn.get("family_id"), record)
    return {"ok": True}
