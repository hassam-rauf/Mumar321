#!/usr/bin/env python3
"""Create or update the Vapi voice assistant from vapi/assistant.json.

Usage: python3 scripts/vapi_setup.py [--dry-run]

Reads from .env:
  VAPI_API_KEY        Vapi private API key (dashboard -> API Keys)
  PUBLIC_URL          HTTPS URL of webhook_server.py, e.g. https://xyz.trycloudflare.com
  VAPI_SECRET         optional shared secret; Vapi sends it as x-vapi-secret, the server checks it
  TRANSFER_NUMBER     optional E.164 number for live transfers, e.g. +15551234567
  VAPI_ASSISTANT_ID   optional; when set the existing assistant is updated instead of created
--dry-run prints the payload without calling Vapi.
"""
import json, os, sys, urllib.error, urllib.request
from pathlib import Path

from woo import load_env

load_env()
ROOT = Path(__file__).resolve().parent.parent
API = "https://api.vapi.ai"


def build_payload():
    public_url = os.environ.get("PUBLIC_URL", "").rstrip("/")
    if not public_url.startswith("https://"):
        sys.exit("PUBLIC_URL must be the HTTPS tunnel URL of webhook_server.py (Vapi cannot reach localhost).")
    server = {"url": f"{public_url}/vapi"}
    if os.environ.get("VAPI_SECRET"):
        server["secret"] = os.environ["VAPI_SECRET"]

    assistant = json.loads((ROOT / "vapi" / "assistant.json").read_text())
    assistant["server"] = server  # end-of-call reports
    tools = assistant["model"]["tools"]
    for tool in tools:
        if tool["type"] == "function":
            tool["server"] = server
    number = os.environ.get("TRANSFER_NUMBER", "").strip()
    if number:
        tools.append({"type": "transferCall", "destinations": [
            {"type": "number", "number": number, "message": "Connecting you to our team now."}]})
    else:
        print("Note: TRANSFER_NUMBER not set, so the agent will take callbacks instead of transferring.")
    return assistant


def call(method, path, payload):
    req = urllib.request.Request(API + path, json.dumps(payload).encode(), method=method, headers={
        "Authorization": f"Bearer {os.environ['VAPI_API_KEY']}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"Vapi API error {e.code}: {e.read().decode(errors='replace')}")


if __name__ == "__main__":
    payload = build_payload()
    if "--dry-run" in sys.argv:
        print(json.dumps(payload, indent=2))
        sys.exit(0)
    if not os.environ.get("VAPI_API_KEY"):
        sys.exit("Set VAPI_API_KEY in .env first.")
    assistant_id = os.environ.get("VAPI_ASSISTANT_ID", "").strip()
    if assistant_id:
        res = call("PATCH", f"/assistant/{assistant_id}", payload)
        print(f"Updated assistant {res['id']}")
    else:
        res = call("POST", "/assistant", payload)
        print(f"Created assistant {res['id']}  (add VAPI_ASSISTANT_ID={res['id']} to .env to update it later)")
    print("Test it: Vapi dashboard -> Assistants -> 'Woo Store Voice Agent' -> Talk to Assistant")
