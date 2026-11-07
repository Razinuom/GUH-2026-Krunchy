"""Create or update the ElevenLabs agent and its webhook tools from agent_spec.py.

    python -m backend.voice.provision --dry-run     # print the JSON that would be sent (no key needed)
    python -m backend.voice.provision               # create/update for real

Needs in .env: ELEVENLABS_API_KEY, PUBLIC_BASE_URL (a public https URL that reaches this backend, e.g. ngrok),
optionally HEIRLOOM_TOOL_SECRET, ELEVENLABS_VOICE_ID / ELEVENLABS_TTS_MODEL / ELEVENLABS_LLM, and
ELEVENLABS_AGENT_ID (if set, that agent is updated instead of creating a new one).
Tool IDs are remembered in backend/voice/elevenlabs_ids.json so re-running updates rather than duplicates.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx

from . import agent_spec
from .config import settings

IDS_FILE = Path(__file__).with_name("elevenlabs_ids.json")


def _load_ids() -> dict:
    return json.loads(IDS_FILE.read_text()) if IDS_FILE.exists() else {"tools": {}}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="print payloads, call nothing")
    args = ap.parse_args(argv)
    s = settings()
    base = s.public_base_url or "https://YOUR-PUBLIC-URL.example"

    tool_payloads = {t["name"]: agent_spec.tool_payload(t, base, s.tool_secret) for t in agent_spec.TOOLS}
    if args.dry_run:
        for name, payload in tool_payloads.items():
            print(f"# POST /v1/convai/tools  ({name})\n{json.dumps(payload, indent=2)}\n")
        print("# POST /v1/convai/agents/create")
        print(json.dumps(agent_spec.agent_payload(["<tool ids>"], s.voice_id, s.tts_model, s.llm), indent=2))
        return 0

    if not s.api_key:
        print("ELEVENLABS_API_KEY is not set (see .env)", file=sys.stderr)
        return 1
    if not s.public_base_url.startswith("https://"):
        print("PUBLIC_BASE_URL must be a public https URL ElevenLabs can reach (e.g. `ngrok http 8000`)",
              file=sys.stderr)
        return 1

    ids = _load_ids()
    headers = {"xi-api-key": s.api_key, "Content-Type": "application/json"}
    with httpx.Client(base_url=s.api_base, headers=headers, timeout=30) as client:
        tool_ids = []
        for name, payload in tool_payloads.items():
            existing = ids["tools"].get(name)
            r = client.patch(f"/v1/convai/tools/{existing}", json=payload) if existing else None
            if r is None or r.status_code == 404:
                r = client.post("/v1/convai/tools", json=payload)
            if r.status_code >= 300:
                print(f"tool {name}: {r.status_code} {r.text}", file=sys.stderr)
                return 1
            ids["tools"][name] = r.json().get("id", existing)
            tool_ids.append(ids["tools"][name])
            print(f"tool {name}: {ids['tools'][name]}")

        payload = agent_spec.agent_payload(tool_ids, s.voice_id, s.tts_model, s.llm)
        agent_id = s.agent_id or ids.get("agent_id")
        if agent_id:
            r = client.patch(f"/v1/convai/agents/{agent_id}", json=payload)
        else:
            r = client.post("/v1/convai/agents/create", json=payload)
        if r.status_code >= 300:
            print(f"agent: {r.status_code} {r.text}", file=sys.stderr)
            return 1
        ids["agent_id"] = agent_id or r.json()["agent_id"]
    IDS_FILE.write_text(json.dumps(ids, indent=2))
    print(f"agent: {ids['agent_id']}")
    if not s.agent_id:
        print(f"\nAdd this to .env:\nELEVENLABS_AGENT_ID={ids['agent_id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
