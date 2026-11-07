import hashlib
import hmac
import json
import time
from datetime import date

import pytest
from fastapi.testclient import TestClient

from backend import main
from backend.heirloom import service, synth
from backend.voice import agent_spec, kb_search, provision
from backend.voice.events import bus
from backend.voice.router import verify_elevenlabs_signature

AS_OF = date(2026, 11, 7)
SECRET = "test-tool-secret"
H = {agent_spec.TOOL_SECRET_HEADER: SECRET}


@pytest.fixture(scope="module")
def tx():
    return synth.generate(AS_OF)


@pytest.fixture()
def client(tx, monkeypatch, tmp_path):
    monkeypatch.setenv("HEIRLOOM_AS_OF", AS_OF.isoformat())
    for k in ("ELEVENLABS_API_KEY", "ELEVENLABS_AGENT_ID", "ELEVENLABS_WEBHOOK_SECRET"):
        monkeypatch.setenv(k, "")
    monkeypatch.setenv("HEIRLOOM_TOOL_SECRET", SECRET)
    monkeypatch.setattr(service, "load_transactions", lambda as_of: tx)
    monkeypatch.setattr("backend.voice.router.LOG_DIR", tmp_path)
    service.clear_caches()
    bus.recent.clear()
    with TestClient(main.app) as c:
        yield c
    service.clear_caches()


# ---------------------------------------------------------------- tools
def test_forecast_tool_returns_speakable_numbers_and_updates_dashboard(client):
    r = client.post("/voice/tools/get_cash_forecast", headers=H,
                    json={"member_id": "tomasz", "language": "pl", "question": "Will I run out of money?"})
    assert r.status_code == 200
    body = r.json()
    assert body["current_balance"] == 2450
    assert body["risk_level"] == "watch"
    assert 5 <= body["chance_overdrawn_next_90_days_percent"] <= 30
    assert "1 in" in body["chance_overdrawn_in_words"]
    assert any(x["reason"] == "Rent increase" for x in body["main_reasons"])
    assert "£" in body["summary_en"]
    ev = bus.recent[-1]
    assert ev["type"] == "forecast" and ev["family_id"] == "nowak"
    assert ev["data"]["spoken_language"] == {"code": "pl", "name": "Polish"}
    assert ev["data"]["forecast"]["days"][0]["d"] == 0  # full English forecast for the dashboard


def test_what_if_gift_increases_risk(client):
    r = client.post("/voice/tools/what_if_payment", headers=H,
                    json={"member_id": "halina", "amount": 2500, "days_from_now": 10,
                          "description": "Gift to Zofia", "language": "pl"})
    body = r.json()
    assert r.status_code == 200
    assert body["chance_overdrawn_after_percent"] >= body["chance_overdrawn_before_percent"]
    assert body["verdict"].split(":")[0] in {"affordable", "tight", "risky"}
    small = client.post("/voice/tools/what_if_payment", headers=H,
                        json={"member_id": "halina", "amount": 100, "language": "pl"}).json()
    assert small["verdict"].startswith("affordable")
    assert bus.recent[-1]["type"] == "what_if"


def test_rules_lookup_cites_govuk(client):
    body = client.post("/voice/tools/lookup_money_rules", headers=H,
                       json={"query": "Lifetime ISA government bonus", "language": "pl"}).json()
    assert body["found"]
    assert any("gov.uk/lifetime-isa" in p["url"] for p in body["passages"])


def test_handoff_logs_and_returns_contacts(client, tmp_path):
    body = client.post("/voice/tools/talk_to_a_person", headers=H,
                       json={"member_id": "daniel", "reason": "debt", "summary": "Worried about rent",
                             "language": "en"}).json()
    assert body["handoff_logged"]
    assert body["contacts"][0]["name"].startswith("StepChange")
    assert (tmp_path / "escalations.jsonl").read_text().count("daniel") == 1
    assert bus.recent[-1]["type"] == "escalation" and bus.recent[-1]["family_id"] == "okafor"
    scam = client.post("/voice/tools/talk_to_a_person", headers=H,
                       json={"member_id": "halina", "reason": "scam", "language": "pl"}).json()
    assert scam["contacts"][0]["phone"] == "159"


def test_tools_require_secret(client):
    r = client.post("/voice/tools/get_cash_forecast", json={"member_id": "tomasz", "language": "en"})
    assert r.status_code == 401
    r = client.post("/voice/tools/get_cash_forecast", headers={agent_spec.TOOL_SECRET_HEADER: "wrong"},
                    json={"member_id": "tomasz", "language": "en"})
    assert r.status_code == 401


def test_unknown_member_404(client):
    r = client.post("/voice/tools/get_cash_forecast", headers=H, json={"member_id": "bob", "language": "en"})
    assert r.status_code == 404


# ---------------------------------------------------------------- session / status / events
def test_session_without_key_is_503_and_status_hides_secrets(client):
    assert client.get("/voice/session?member_id=halina").status_code == 503
    st = client.get("/voice/status").json()
    assert st["configured"] is False and st["tool_secret_set"] is True
    assert SECRET not in json.dumps(st)


def test_session_returns_signed_url_and_dynamic_variables(client, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk_test")
    monkeypatch.setenv("ELEVENLABS_AGENT_ID", "agent_test")
    calls = {}

    class FakeResp:
        status_code = 200

        def json(self):
            return {"signed_url": "wss://example/convai?token=abc"}

    class FakeClient:
        def __init__(self, *a, **k): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *a): pass

        async def get(self, url, params=None, headers=None):
            calls.update(url=url, params=params, headers=headers)
            return FakeResp()

    monkeypatch.setattr("backend.voice.router.httpx.AsyncClient", FakeClient)
    body = client.get("/voice/session?member_id=halina").json()
    assert body["signed_url"].startswith("wss://")
    assert body["dynamic_variables"] == {"member_id": "halina", "member_name": "Halina", "family_id": "nowak"}
    assert calls["params"] == {"agent_id": "agent_test"} and calls["headers"]["xi-api-key"] == "sk_test"
    assert "sk_test" not in json.dumps(body)


def test_recent_events_filter_by_family(client):
    client.post("/voice/tools/get_cash_forecast", headers=H, json={"member_id": "grace", "language": "en"})
    assert client.get("/voice/events/recent?family_id=nowak").json() == []
    assert client.get("/voice/events/recent?family_id=okafor").json()[-1]["data"]["member_id"] == "grace"


# ---------------------------------------------------------------- post-call webhook
def _sign(secret, body: bytes, t=None):
    t = str(int(t or time.time()))
    return f"t={t},v0=" + hmac.new(secret.encode(), f"{t}.{body.decode()}".encode(), hashlib.sha256).hexdigest()


def test_signature_verification():
    body = b'{"type":"post_call_transcription"}'
    assert verify_elevenlabs_signature(body, _sign("s", body), "s")
    assert not verify_elevenlabs_signature(body, _sign("other", body), "s")
    assert not verify_elevenlabs_signature(body, _sign("s", body, t=time.time() - 7200), "s")
    assert not verify_elevenlabs_signature(body, None, "s")


def test_post_call_webhook(client, monkeypatch, tmp_path):
    monkeypatch.setenv("ELEVENLABS_WEBHOOK_SECRET", "whsec")
    body = json.dumps({"type": "post_call_transcription", "data": {
        "conversation_id": "conv_1", "transcript": [{"role": "user", "message": "Dzień dobry"}],
        "analysis": {"transcript_summary": "Halina asked about her balance."},
        "conversation_initiation_client_data": {"dynamic_variables": {"member_id": "halina", "family_id": "nowak"}}}}).encode()
    assert client.post("/voice/webhooks/post-call", content=body).status_code == 401
    r = client.post("/voice/webhooks/post-call", content=body, headers={"ElevenLabs-Signature": _sign("whsec", body)})
    assert r.status_code == 200
    assert "conv_1" in (tmp_path / "conversations.jsonl").read_text()
    assert bus.recent[-1]["type"] == "call_ended"


# ---------------------------------------------------------------- agent spec / provisioning
def test_agent_payload_has_polish_and_guardrails():
    p = agent_spec.agent_payload(["t1", "t2"])
    agent = p["conversation_config"]["agent"]
    assert agent["prompt"]["tool_ids"] == ["t1", "t2"]
    assert agent["prompt"]["built_in_tools"]["language_detection"]["params"]["system_tool_type"] == "language_detection"
    assert "pl" in p["conversation_config"]["language_presets"]
    assert "not regulated financial advice" in agent["prompt"]["prompt"]
    assert set(agent["dynamic_variables"]["dynamic_variable_placeholders"]) == {"member_id", "member_name", "family_id"}


def test_every_tool_spec_has_a_route():
    paths = set(main.app.openapi()["paths"])
    for t in agent_spec.TOOLS:
        assert t["path"] in paths
        payload = agent_spec.tool_payload(t, "https://x.example", SECRET)["tool_config"]
        assert payload["api_schema"]["url"] == "https://x.example" + t["path"]
        assert payload["api_schema"]["request_headers"][agent_spec.TOOL_SECRET_HEADER] == SECRET
        assert set(t["body"]["required"]) <= set(t["body"]["properties"])


def test_provision_dry_run(capsys):
    assert provision.main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "get_cash_forecast" in out and "/v1/convai/agents/create" in out


def test_kb_search_ranks_relevant_pages():
    hits = kb_search.search("inheritance tax gifts 7 year rule")
    assert hits and "inheritance-tax" in hits[0]["url"]
    assert kb_search.search("") == []


# ---------------------------------------------------------------- languages
def test_agent_supports_english_polish_malay_mandarin():
    p = agent_spec.agent_payload(["t1"])
    conv = p["conversation_config"]
    assert conv["agent"]["language"] == "en"
    assert set(conv["language_presets"]) == {"pl", "ms", "zh"}
    assert "您好" in conv["language_presets"]["zh"]["overrides"]["agent"]["first_message"]
    assert "Selamat" in conv["language_presets"]["ms"]["overrides"]["agent"]["first_message"]
    prompt = conv["agent"]["prompt"]["prompt"]
    assert "{{LANGUAGE_" not in prompt  # build-time placeholders all filled
    assert "{{member_name}}" in prompt  # runtime dynamic variables untouched
    for name in ("English", "Polish", "Malay", "Mandarin Chinese", "英镑", "paun"):
        assert name in prompt


def test_language_enum_on_every_tool():
    for t in agent_spec.TOOLS:
        assert t["body"]["properties"]["language"]["enum"] == ["en", "pl", "ms", "zh"]


@pytest.mark.parametrize("code,name", [("ms", "Malay"), ("zh", "Mandarin Chinese"), ("zh-CN", "Mandarin Chinese")])
def test_dashboard_event_names_spoken_language(client, code, name):
    client.post("/voice/tools/get_cash_forecast", headers=H, json={"member_id": "ada", "language": code})
    assert bus.recent[-1]["data"]["spoken_language"]["name"] == name


def test_voice_test_page_served(client):
    r = client.get("/voice/test")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert "@elevenlabs/client@1.29.0" in r.text and "/voice/session" in r.text
