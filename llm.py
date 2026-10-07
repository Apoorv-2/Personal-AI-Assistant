import json, re
from datetime import datetime
from config import HF_MODEL
import os

_pipe = None
def _load():
    global _pipe
    if _pipe is None:
        from transformers import pipeline
        _pipe = pipeline("text-generation", model=HF_MODEL, device_map="auto", dtype="auto")
    return _pipe

def chat(messages, max_new_tokens=300):
    out = _load()(messages, max_new_tokens=max_new_tokens, do_sample=False)
    return out[0]["generated_text"][-1]["content"]

def _clean(d):
    for k, v in list(d.items()):
        if isinstance(v, str) and v.strip().lower() in ("null", "none", "", "n/a"):
            d[k] = None
    d["attendees"] = [a for a in (d.get("attendees") or [])
                      if isinstance(a, str) and a.strip().lower() not in ("null", "none", "")]
    return d

SYSTEM = """You are an executive assistant's intent parser. Today is {today}.
Reply with ONLY one JSON object: {{"intent": one of [schedule_meeting, list_events, daily_summary, send_email, delete_event, chitchat],
"title": str, "attendees": [str], "date": "YYYY-MM-DD" or null, "time": "HH:MM" or null, "duration_min": int,
"to": str, "subject": str, "body": str}}. Use null for unknown fields."""
