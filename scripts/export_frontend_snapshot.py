"""Save real backend results for the website's offline mode.

    python scripts/export_frontend_snapshot.py      # writes frontend/src/data/snapshot.json

If the API is unreachable during the demo, the website shows these saved results (marked
"offline snapshot") instead of anything made up. Re-run after changing personas or models.
It calls the API in-process, exactly as the browser does, for the demo date (HEIRLOOM_AS_OF,
default 2026-11-07).
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("HEIRLOOM_AS_OF", "2026-11-07")

from fastapi.testclient import TestClient  # noqa: E402

from backend.main import app  # noqa: E402
from backend.voice.router import HELP, HELP_BY_REASON  # noqa: E402

OUT = ROOT / "frontend" / "src" / "data" / "snapshot.json"
CLAIM_EXAMPLES = [
    "This stock is guaranteed to 10x by Christmas. DM me to join before it's too late!",
    "The Lifetime ISA adds a 25% bonus on up to £4,000 a year.",
    "You can give away £3,000 a year with no inheritance tax, and anything else is tax-free after 7 years.",
]


def tm_key(req: dict) -> str:
    """Must match timeMachineKey() in frontend/src/lib/api.ts."""
    return f"{req['family_id']}|{req['gift']:g}|{req['timing']}|{req['monthly_saving']:g}|{str(req['lisa']).lower()}"


def main() -> None:
    with TestClient(app) as c:
        def get(path):
            r = c.get(path)
            r.raise_for_status()
            return r.json()

        def post(path, body):
            r = c.post(path, json=body)
            r.raise_for_status()
            return r.json()

        health = get("/health")
        families = get("/families")
        members = [m["id"] for f in families for m in f["members"]]
        timemachine = {}
        for f in families:
            ctl = f["time_machine"]["controls"]
            for timing in ("now", "10y", "inheritance"):
                req = {"family_id": f["id"], "gift": ctl["gift"], "timing": timing,
                       "monthly_saving": ctl["monthly_saving"], "lisa": ctl["lisa"]}
                timemachine[tm_key(req)] = post("/timemachine", req)
        snapshot = {
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "as_of": health["as_of"],
            "families": families,
            "forecasts": {m: post("/forecast", {"member_id": m}) for m in members},
            "hardship": {m: post("/hardship", {"member_id": m}) for m in members},
            "timemachine": timemachine,
            "claims": {claim: post("/claimcheck", {"claim": claim}) for claim in CLAIM_EXAMPLES},
            "help": {reason: [HELP[k] for k in keys] for reason, keys in HELP_BY_REASON.items()},
        }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(snapshot, indent=1, ensure_ascii=False))
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1024:.0f} KB) for {health['as_of']}: "
          f"{len(members)} members, {len(timemachine)} Time Machine scenarios, {len(CLAIM_EXAMPLES)} claims")


if __name__ == "__main__":
    main()
