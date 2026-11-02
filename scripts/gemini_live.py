"""Gemini Live adapter: a free live voice call in the browser, on the same backend as Vapi.

The browser (demo/gemini_call.html) talks to the Gemini Live API directly over a WebSocket.
This module gives it what it needs without exposing GEMINI_API_KEY:
  session()     a single-use ephemeral token plus the setup (prompt, voice, tools) built from
                vapi/assistant.json, so Vapi and Gemini share one prompt and one tool list.
  tool_call()   runs a Gemini function call through the normal webhook contract and returns the
                same text the Vapi adapter returns.
"""
import json, os, urllib.error, urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from vapi_adapter import to_result_text

ASSISTANT = Path(__file__).resolve().parent.parent / "vapi" / "assistant.json"
TOKEN_URL = "https://generativelanguage.googleapis.com/v1beta/auth_tokens"


class GeminiError(Exception):
    pass


def _schema(s):
    """OpenAI-style JSON schema -> Gemini schema (upper-case types, no empty objects)."""
    out = {"type": s.get("type", "string").upper()}
    if s.get("description"):
        out["description"] = s["description"]
    if s.get("properties"):
        out["properties"] = {k: _schema(v) for k, v in s["properties"].items()}
    if s.get("required"):
        out["required"] = s["required"]
    return out


def setup():
    a = json.loads(ASSISTANT.read_text(encoding="utf-8"))
    prompt = a["model"]["messages"][0]["content"]
    # No live transfers in the browser demo: the business_hours result always says "take a callback".
    prompt += ("\n\nThis call runs in a web browser. When the call starts, greet the caller with exactly: "
               f"\"{a['firstMessage']}\" When you end the call, say: \"{a['endCallMessage']}\"")
    functions = []
    for t in a["model"]["tools"]:
        if t["type"] != "function":
            continue
        fn = {"name": t["function"]["name"], "description": t["function"]["description"]}
        params = t["function"].get("parameters") or {}
        if params.get("properties"):  # Gemini rejects OBJECT parameters with no properties
            fn["parameters"] = _schema(params)
        functions.append(fn)
    if any(t["type"] == "endCall" for t in a["model"]["tools"]):  # handled in the browser: hangs up
        functions.append({"name": "end_call", "description": "Hang up after saying goodbye, when the caller is done."})
    return {
        "model": "models/" + os.environ.get("GEMINI_MODEL", "gemini-3.8-live"),
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {
                "voiceName": os.environ.get("GEMINI_VOICE", "Kore")}}},
        },
        "systemInstruction": {"parts": [{"text": prompt}]},
        "tools": [{"functionDeclarations": functions}],
        "inputAudioTranscription": {},
        "outputAudioTranscription": {},
    }


def session():
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise GeminiError("GEMINI_API_KEY is not set in .env (free key: https://aistudio.google.com/apikey).")
    now = datetime.now(timezone.utc)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    body = {"uses": 1, "expireTime": (now + timedelta(minutes=30)).strftime(fmt),
            "newSessionExpireTime": (now + timedelta(minutes=2)).strftime(fmt)}
    req = urllib.request.Request(TOKEN_URL, json.dumps(body).encode(), method="POST", headers={
        "x-goog-api-key": key, "Content-Type": "application/json", "User-Agent": "woo-support-agent/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            token = json.loads(r.read())["name"]
    except urllib.error.HTTPError as e:
        raise GeminiError(f"Gemini token error {e.code}: {e.read().decode(errors='replace')[:300]}")
    except urllib.error.URLError as e:
        raise GeminiError(f"Could not reach Gemini: {e.reason}")
    return {"token": token, "setup": setup()}


def tool_call(body, handle):
    """body: {"name", "args"} from the browser. handle: the webhook's handle() function."""
    name, args = body.get("name"), body.get("args") or {}
    res = handle({"action": name, "payload": args})
    print(f"gemini tool {name} {json.dumps(args)}: ok={res['ok']} route={res.get('route')}")
    print(f"  -> {res['message']}", flush=True)
    return {"result": to_result_text(res)}
