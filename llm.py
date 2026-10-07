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
    d["attendees"] = [a for a in (d.get("attendees") or []) if isinstance(a, str) and a.strip().lower() not in ("null", "none", "")]
    return d

SYSTEM = """You are an executive assistant's intent parser. Today is {today}.
Reply with ONLY one JSON object: {{"intent": one of [schedule_meeting, list_events, daily_summary, send_email, delete_event, chitchat],
"title": str, "attendees": [str], "date": "YYYY-MM-DD" or null, "time": "HH:MM" or null, "duration_min": int,
"to": str, "subject": str, "body": str}}. Use null for unknown fields."""

def parse_intent(text, history):
    if os.getenv("USE_LLM", "1") == "0":
        return rule_fallback(text)
    msgs = [{"role": "system", "content": SYSTEM.format(today=datetime.now().strftime("%A %Y-%m-%d"))}] + history[-4:] + \
           [{"role": "user", "content": text}]
    try:
        raw = chat(msgs, 200)
        return _clean(json.loads(re.search(r"\{.*\}", raw, re.S).group(0)))
    except Exception:
        return _clean(rule_fallback(text))          # small models sometimes break JSON

def rule_fallback(t):
    l = t.lower()
    d = {"intent": "chitchat", "attendees": [], "duration_min": 30, "date": None, "time": None, "title": "Meeting"}
    if re.search(r"delete|cancel|remove", l): 
        d["intent"] = "delete_event"
    elif re.search(r"summary|brief|today|agenda", l): 
        d["intent"] = "daily_summary"
    elif re.search(r"email|mail", l): 
        d.update(intent="send_email", to=(re.findall(r"[\w.]+@[\w.]+", t) or [""])[0], subject="Follow-up", body=t)
    elif re.search(r"schedule|meet|book|set up", l):
        d["intent"] = "schedule_meeting"
        d["attendees"] = re.findall(r"with ([A-Z][a-z]+)", t)
        m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", l)
        if m:
            h = int(m[1]) % 12 + (12 if m[3] == "pm" else 0); d["time"] = f"{h:02d}:{m[2] or '00'}"
    elif re.search(r"events|calendar|free|schedule", l): 
        d["intent"] = "list_events"
    return d

def summarize(events, emails):
    prompt = f"Write a 3-sentence friendly daily brief.\nEvents: {events}\nEmails: {emails}"
    try: 
        return chat([{"role": "user", "content": prompt}], 150)
    except Exception: 
        return f"{len(events)} event(s) and {len(emails)} new email(s) today."
