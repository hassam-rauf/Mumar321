"""Vapi adapter: turns Vapi server messages into the existing webhook contract.

Vapi POSTs every server event to one URL as {"message": {"type": ..., ...}}.
For "tool-calls" it expects {"results": [{"toolCallId": ..., "result": "<text>"}]} back.
Each tool name is one of the webhook actions (track_order, check_stock, ...), and the tool
arguments are the action payload, so the voice agent reuses the same backend as Voiceflow/Make.

Other events (status-update, end-of-call-report, ...) are acknowledged; end-of-call reports are
appended to data/calls.jsonl so the demo can show what happened on each call.
"""
import json
from datetime import datetime
from pathlib import Path

CALL_LOG = Path(__file__).resolve().parent.parent / "data" / "calls.jsonl"

# What the assistant should do next, based on the webhook's "route" field.
ROUTE_HINTS = {
    "transfer": " NEXT STEP: tell the caller you are connecting them, then call the transferCall tool.",
    "message": " NEXT STEP: ask for their name, phone number and reason for calling, then call callback_request.",
}


def _arguments(fn):
    args = fn.get("arguments") or {}
    if isinstance(args, str):  # some Vapi versions send the arguments as a JSON string
        try:
            args = json.loads(args or "{}")
        except ValueError:
            args = {}
    return args if isinstance(args, dict) else {}


def _tool_calls(message):
    """Yield (id, name, arguments) from either list Vapi may send."""
    calls = message.get("toolCallList")
    if calls is None:
        calls = [t.get("toolCall") or {} for t in message.get("toolWithToolCallList") or []]
    for call in calls or []:
        fn = call.get("function") or {}
        yield call.get("id"), fn.get("name"), _arguments(fn)


def to_result_text(res):
    return res["message"] + ROUTE_HINTS.get(res.get("route") or "", "")


def handle_vapi(body, handle):
    """body: parsed Vapi request. handle: the webhook's handle({"action", "payload"}) function."""
    message = (body or {}).get("message") or {}
    kind = message.get("type")

    if kind == "tool-calls":
        results = []
        for call_id, name, args in _tool_calls(message):
            res = handle({"action": name, "payload": args})
            results.append({"toolCallId": call_id, "result": to_result_text(res)})
            print(f"vapi tool {name}: ok={res['ok']} route={res.get('route')}")
        return {"results": results}

    if kind == "end-of-call-report":
        call = message.get("call") or {}
        artifact = message.get("artifact") or {}
        entry = {
            "at": datetime.now().isoformat(timespec="seconds"),
            "call_id": call.get("id"),
            "ended_reason": message.get("endedReason"),
            "summary": (message.get("analysis") or {}).get("summary") or message.get("summary"),
            "transcript": artifact.get("transcript") or message.get("transcript"),
            "recording_url": artifact.get("recordingUrl") or message.get("recordingUrl"),
        }
        CALL_LOG.parent.mkdir(exist_ok=True)
        with CALL_LOG.open("a") as f:
            f.write(json.dumps(entry) + "\n")
        print(f"vapi call ended: {entry['ended_reason']}")

    return {}  # status-update, transcript, hang, etc.: nothing to return
