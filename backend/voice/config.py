"""Voice settings, read from the environment / .env at the repo root."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
except ImportError:  # python-dotenv is optional; plain env vars still work
    pass

PLACEHOLDER_PREFIXES = ("your-", "your_")  # .env.example values; treated as unset


def _get(name: str, default: str = "") -> str:
    v = os.environ.get(name, default).strip()
    return "" if v.lower().startswith(PLACEHOLDER_PREFIXES) else v


@dataclass(frozen=True)
class VoiceSettings:
    api_key: str
    agent_id: str
    api_base: str
    voice_id: str
    tts_model: str
    llm: str
    tool_secret: str
    webhook_secret: str
    public_base_url: str

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.agent_id)


def settings() -> VoiceSettings:
    return VoiceSettings(
        api_key=_get("ELEVENLABS_API_KEY"),
        agent_id=_get("ELEVENLABS_AGENT_ID"),
        api_base=_get("ELEVENLABS_API_BASE", "https://api.elevenlabs.io").rstrip("/"),
        voice_id=_get("ELEVENLABS_VOICE_ID"),
        tts_model=_get("ELEVENLABS_TTS_MODEL"),
        llm=_get("ELEVENLABS_LLM"),
        tool_secret=_get("HEIRLOOM_TOOL_SECRET"),
        webhook_secret=_get("ELEVENLABS_WEBHOOK_SECRET"),
        public_base_url=_get("PUBLIC_BASE_URL").rstrip("/"),
    )
