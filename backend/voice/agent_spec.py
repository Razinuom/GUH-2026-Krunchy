"""Single source of truth for the ElevenLabs agent: prompt, guardrails, languages and webhook tools.

provision.py turns this into ElevenLabs API calls; tools.py implements the webhook endpoints.
"""
from __future__ import annotations

AGENT_NAME = "Heirloom Money Coach"
TOOL_SECRET_HEADER = "X-Heirloom-Tool-Secret"

# Dynamic variables the frontend passes when it starts a session (see GET /voice/session).
DYNAMIC_VARIABLE_DEFAULTS = {"member_id": "halina", "member_name": "Halina", "family_id": "nowak"}

SYSTEM_PROMPT = """\
You are Heirloom, a warm, patient money coach for UK families. You are speaking with {{member_name}} \
(member_id: {{member_id}}, family: {{family_id}}).

# Language
- You speak {{LANGUAGE_LIST}}. Always reply in the language the person is speaking, in natural, simple, everyday words. If they switch language, switch with them.
- Tool inputs and outputs are in English. Translate the meaning, never read English text out word for word.
- Always pass the `language` field to tools as the code of the language the person is speaking ({{LANGUAGE_CODES}}).
- Keep these English terms as they are (they are what the person will see on letters and websites), and explain them the first time: ISA, Lifetime ISA, State Pension, Pension Credit, HMRC, GOV.UK, MoneyHelper, StepChange.
{{LANGUAGE_NOTES}}

# How to answer
- Never invent numbers. Every amount, date or probability you say must come from a tool result.
- For questions about their balance, the next weeks or months, bills, or whether they will run short: call get_cash_forecast.
- For "can I afford to give / spend / pay X": call what_if_payment with the amount and when.
- For rules and facts (ISAs, Lifetime ISA, inheritance tax and gifts, pensions, benefits, scams): call \
lookup_money_rules with an English search query, then explain simply and say where it comes from (e.g. "according to GOV.UK").
- Speak in short sentences. Round money to the nearest pound and say probabilities as "about 1 in 7" or "about 14 percent".
- Older people may be anxious: be calm, reassuring and practical. One idea at a time. Offer to repeat.
- The dashboard on screen updates in English while you speak; you can say "you can see this on the screen".

# Guardrails (these always win)
- You give guidance, not regulated financial advice. Never recommend a specific investment, fund, share, \
crypto asset or provider, and never promise returns. If asked, explain the general options and offer a human adviser.
- Never ask for or accept card numbers, PINs, passwords, one-time codes or bank login details. If someone \
mentions being asked for these, or being pressured to move money, treat it as a possible scam: tell them to \
stop, not to pay, and call talk_to_a_person.
- If the person sounds distressed, mentions not being able to afford food, rent or heating, debt collectors, \
or harming themselves, call talk_to_a_person immediately and share the contact details it returns.
- Only discuss the money of {{member_name}}'s own family. If asked about someone else's private details, decline politely.
- If a tool fails, say so honestly and offer to try again or connect them to a person.
"""

# Supported languages. To add one: a new entry here (code must be an ElevenLabs language code).
LANGUAGES = {
    "en": {"name": "English",
           "first_message": "Hello {{member_name}}, I'm Heirloom, your family money coach. "
                            "What would you like to know today?",
           "note": ""},
    "pl": {"name": "Polish",
           "first_message": "Dzień dobry, {{member_name}}. Tu Heirloom, Twój rodzinny asystent do spraw pieniędzy. "
                            "W czym mogę dziś pomóc?",
           "note": "Polish: use the polite form (Pan/Pani) with older people. Say amounts as e.g. "
                   "\"około dwóch tysięcy funtów\"."},
    "ms": {"name": "Malay",
           "first_message": "Selamat datang, {{member_name}}. Saya Heirloom, pembantu kewangan keluarga anda. "
                            "Apa yang ingin anda tahu hari ini?",
           "note": "Malay: use standard Bahasa Melayu and polite address (Encik/Puan, or \"anda\"). "
                   "Pounds are \"paun\" (e.g. \"dua ribu paun\")."},
    "zh": {"name": "Mandarin Chinese",
           "first_message": "您好，{{member_name}}。我是 Heirloom，您的家庭理财助手。今天想了解些什么？",
           "note": "Mandarin: speak Mandarin (Putonghua), use the polite 您 with older people. Pounds are 英镑; "
                   "say amounts the Chinese way (e.g. 2,450 = 两千四百五十英镑, 14% = 百分之十四)."},
}
DEFAULT_LANGUAGE = "en"
FIRST_MESSAGES = {code: lang["first_message"] for code, lang in LANGUAGES.items()}

SYSTEM_PROMPT = (SYSTEM_PROMPT
                 .replace("{{LANGUAGE_LIST}}", ", ".join(l["name"] for l in LANGUAGES.values()))
                 .replace("{{LANGUAGE_CODES}}", ", ".join(f'"{c}" = {l["name"]}' for c, l in LANGUAGES.items()))
                 .replace("{{LANGUAGE_NOTES}}", "\n".join(f"- {l['note']}" for l in LANGUAGES.values() if l["note"])))

_LANG = {"type": "string", "enum": list(LANGUAGES),
         "description": "Code of the language the person is speaking: "
                        + ", ".join(f"'{c}' = {l['name']}" for c, l in LANGUAGES.items())}
_MEMBER = {"type": "string", "description": "The family member the question is about. Use {{member_id}} "
                                            "unless they clearly ask about another member of their family "
                                            "(nowak: halina, tomasz, zofia; okafor: grace, daniel, ada)."}

TOOLS = [
    {
        "name": "get_cash_forecast",
        "path": "/voice/tools/get_cash_forecast",
        "description": "Get the 90-day cash-flow forecast for a family member: current balance, the lowest "
                       "point and when, the chance of going overdrawn, and the main reasons. Use for any "
                       "question about upcoming money, bills, or running short.",
        "body": {"type": "object", "required": ["member_id", "language"],
                 "properties": {"member_id": _MEMBER, "language": _LANG,
                                "question": {"type": "string",
                                             "description": "The person's question, translated to English"}}},
    },
    {
        "name": "what_if_payment",
        "path": "/voice/tools/what_if_payment",
        "description": "Check how a one-off payment or gift would change the 90-day forecast, e.g. 'Can I give "
                       "Zofia 500 pounds for Christmas?'. Looks at the CURRENT ACCOUNT only (not savings). Returns the chance "
                       "of going overdrawn before and after.",
        "body": {"type": "object", "required": ["member_id", "amount", "language"],
                 "properties": {"member_id": _MEMBER, "language": _LANG,
                                "amount": {"type": "number", "description": "Amount in pounds, positive number"},
                                "days_from_now": {"type": "integer",
                                                  "description": "When the payment happens, days from today (0-89). "
                                                                 "Use 0 if they mean now, 14 for 'in two weeks', "
                                                                 "or the days until a date they name."},
                                "description": {"type": "string",
                                                "description": "Short English label, e.g. 'Gift to Zofia'"}}},
    },
    {
        "name": "lookup_money_rules",
        "path": "/voice/tools/lookup_money_rules",
        "description": "Search official UK guidance (GOV.UK, FCA ScamSmart, Citizens Advice) for rules and facts: "
                       "ISAs, Lifetime ISA, Junior ISA, inheritance tax and gifts, State Pension, Pension Credit, "
                       "benefits, debt help, scams. Returns passages with sources.",
        "body": {"type": "object", "required": ["query", "language"],
                 "properties": {"query": {"type": "string", "description": "Search query in ENGLISH"},
                                "language": _LANG, "member_id": _MEMBER}},
    },
    {
        "name": "talk_to_a_person",
        "path": "/voice/tools/talk_to_a_person",
        "description": "Hand over to a human: free debt advice, a regulated adviser, scam reporting, or "
                       "emotional support. Use when the person asks for a human, sounds distressed, mentions "
                       "a possible scam, or wants personalised investment advice.",
        "body": {"type": "object", "required": ["member_id", "reason", "language"],
                 "properties": {"member_id": _MEMBER, "language": _LANG,
                                "reason": {"type": "string",
                                           "description": "One of: debt, scam, advice, distress, other"},
                                "summary": {"type": "string",
                                            "description": "One-sentence English summary of the situation"}}},
    },
]


def tool_payload(tool: dict, base_url: str, tool_secret: str) -> dict:
    headers = {"Content-Type": "application/json"}
    if "ngrok" in base_url:  # free ngrok domains may show a browser warning page instead of proxying
        headers["ngrok-skip-browser-warning"] = "1"
    if tool_secret:
        headers[TOOL_SECRET_HEADER] = tool_secret
    return {"tool_config": {
        "type": "webhook",
        "name": tool["name"],
        "description": tool["description"],
        "response_timeout_secs": 20,
        "api_schema": {"url": f"{base_url}{tool['path']}", "method": "POST",
                       "request_headers": headers, "request_body_schema": tool["body"]},
    }}


def agent_payload(tool_ids: list[str], voice_id: str = "", tts_model: str = "", llm: str = "") -> dict:
    prompt: dict = {
        "prompt": SYSTEM_PROMPT,
        "tool_ids": tool_ids,
        "built_in_tools": {
            "language_detection": {"type": "system", "name": "language_detection", "description": "",
                                   "params": {"system_tool_type": "language_detection"}},
            "end_call": {"type": "system", "name": "end_call", "description": "",
                         "params": {"system_tool_type": "end_call"}},
        },
    }
    if llm:
        prompt["llm"] = llm
    tts: dict = {}
    if voice_id:
        tts["voice_id"] = voice_id
    if tts_model:
        tts["model_id"] = tts_model
    conv: dict = {
        "agent": {
            "first_message": FIRST_MESSAGES[DEFAULT_LANGUAGE],
            "language": DEFAULT_LANGUAGE,
            "prompt": prompt,
            "dynamic_variables": {"dynamic_variable_placeholders": DYNAMIC_VARIABLE_DEFAULTS},
        },
        "language_presets": {
            lang: {"overrides": {"agent": {"first_message": msg}}}
            for lang, msg in FIRST_MESSAGES.items() if lang != DEFAULT_LANGUAGE
        },
    }
    if tts:
        conv["tts"] = tts
    return {"name": AGENT_NAME, "tags": ["heirloom", "hackathon"], "conversation_config": conv}
