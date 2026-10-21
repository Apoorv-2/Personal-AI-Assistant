from datetime import datetime, timedelta
from memory import ShortTermMemory, LongTermMemory
from guardrails import Guardrail, PendingQueue
from mcp_hub import MCPHub
import llm
import re

hub, queue = MCPHub(), PendingQueue()
guard = Guardrail(hub, queue)
stm, ltm = ShortTermMemory(), LongTermMemory()
DEFAULT_HOURS = [10, 11, 14, 15, 16]

def _date(s):
    if s: return s
    return (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")

def find_slot(date, dur, attendees):
    busy = hub.call("list_events", {"date": date})
    prefs = ltm.preferred_hours(attendees) + DEFAULT_HOURS          # learned habits first
    for h in prefs:
        s, e = datetime.fromisoformat(f"{date}T{h:02d}:00"), datetime.fromisoformat(f"{date}T{h:02d}:00") + timedelta(minutes=dur)
        if all(e <= datetime.fromisoformat(b["start"]) or s >= datetime.fromisoformat(b["end"]) for b in busy):
            return s, e
    return None, None

def handle(sid, text):
    stm.add(sid, "user", text)
    p = llm.parse_intent(text, stm.history(sid))
    low = text.lower()
    if "tomorrow" in low:
        p["date"] = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    elif "today" in low:
        p["date"] = datetime.now().strftime("%Y-%m-%d")
    if not p.get("attendees"):
        m = re.search(r"\bwith\s+([A-Za-z]+)", text)
        if m: p["attendees"] = [m.group(1).title()]
    ctx = stm.ctx[sid]
    for k in ("title", "date", "time", "to", "subject"):
        v = p.get(k)
        if k == "time" and v and not re.fullmatch(r"\d{1,2}:\d{2}", str(v)): v = None
        if k == "date" and v and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(v)): v = None
        if v: ctx[k] = v
    if p.get("attendees"): ctx["attendees"] = p["attendees"]
    intent, reply = p.get("intent"), ""

    if intent == "schedule_meeting":
        att, date, dur = ctx.get("attendees", []), _date(ctx.get("date")), int(p.get("duration_min") or 30)
        if not att:
            reply = "Who should I invite?"
        else:
            if ctx.get("time"): s = datetime.fromisoformat(f"{date}T{ctx['time'].zfill(5)}"); e = s + timedelta(minutes=dur)
            else: s, e = find_slot(date, dur, att)
            if not s: reply = f"No free slot on {date}. Want another day?"
            else:
                r = guard.request("create_event", {"title": ctx.get("title", "Meeting"), "start": s.isoformat(timespec="minutes"),
                                  "end": e.isoformat(timespec="minutes"), "attendees": att},
                                  f"Create '{ctx.get('title','Meeting')}' with {', '.join(att)} on {s:%a %d %b %H:%M}")
                reply = f"I proposed {s:%a %d %b at %H:%M}. Approve it in the panel."
                stm.ctx[sid] = {}
    elif intent == "list_events":
        ev = hub.call("list_events", {"date": _date(p.get("date"))})
        reply = "\n".join(f"{e['start'][11:]} {e['title']}" for e in ev) or "Nothing scheduled."
    elif intent == "daily_summary":
        ev = hub.call("list_events", {"date": datetime.now().strftime("%Y-%m-%d")})
        reply = llm.summarize(ev, hub.call("read_email", {}))
    elif intent == "send_email":
        to = p.get("to") or (re.findall(r"[\w.+-]+@[\w.-]+", text) or [""])[0]
        m = re.search(r"about (.+)", text, re.I)
        topic = m.group(1) if m else "a quick follow-up"
        body = llm.chat([{"role": "user", "content":
                 f"Write a short, polite email (under 120 words, no subject line) about: {topic}. Sign off as Apoorv."}], 200)
        guard.request("send_email", {"to": to, "subject": topic.capitalize(), "body": body},
                      f"Email to {to}: {topic}")
        reply = "Draft ready. Review and edit it in the panel, then approve to send."
    elif intent == "delete_event":
        reply = guard.request("delete_event", {}, "")["reason"] + " Delete it manually in your calendar."
    else:
        reply = llm.chat(stm.history(sid) + [{"role": "user", "content": text}], 120)
    stm.add(sid, "assistant", reply)
    return reply

def on_approved(item):
    """Learn habits from approved meetings."""
    if item["action"] == "create_event":
        h = int(item["params"]["start"][11:13])
        for n in item["params"].get("attendees", []): ltm.record_meeting(n, h)
