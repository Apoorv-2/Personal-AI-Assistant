import asyncio, uuid
from datetime import datetime, timedelta
from config import USE_MOCK_MCP, MCP_SERVERS, TOOL_MAP
from middleware import middleware
import smtplib
from email.message import EmailMessage
from config import SMTP_USER, SMTP_PASSWORD

def smtp_send(to, subject, body):
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = SMTP_USER, to, subject
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(SMTP_USER, SMTP_PASSWORD)
        s.send_message(msg)
    return {"sent": True, "to": to}

class MockBackend:
    def __init__(self):
        d = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        self.events = [{"id": "e1", "title": "Team standup", "start": f"{d}T10:00", "end": f"{d}T10:30", "attendees": []},
                       {"id": "e2", "title": "Lunch", "start": f"{d}T13:00", "end": f"{d}T14:00", "attendees": []}]
        self.emails = [{"from": "boss@corp.com", "subject": "Q4 planning", "snippet": "Can we sync this week?"}]
    def call(self, action, p):
        if action == "list_events":
            if "days" in p:
                today = datetime.now().strftime("%Y-%m-%d")
                end = (datetime.now() + timedelta(days=p["days"])).strftime("%Y-%m-%d")
                return sorted([e for e in self.events if today <= e["start"][:10] < end], key=lambda e: e["start"])
            return [e for e in self.events if e["start"].startswith(p.get("date", ""))]
        if action == "create_event":
            e = {"id": uuid.uuid4().hex[:6], **{k: p[k] for k in ("title", "start", "end")}, "attendees": p.get("attendees", [])}
            self.events.append(e); return e
        if action == "read_email": return self.emails
        if action == "send_email": return {"sent": True, "to": p["to"]}
        if action == "post_slack": return {"posted": True}
        raise ValueError(action)

class MCPHub:
    def __init__(self): self.mock = MockBackend() if USE_MOCK_MCP else None
    @middleware(key_arg=1)
    def call(self, action, params):
        if action == "send_email" and SMTP_USER:
            return smtp_send(params["to"], params["subject"], params["body"])
        if self.mock: return self.mock.call(action, params)
        server, tool = TOOL_MAP[action]
        return asyncio.run(self._real(server, tool, params))
    async def _real(self, server, tool, args):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        cfg = MCP_SERVERS[server]
        params = StdioServerParameters(command=cfg["command"], args=cfg["args"], env=cfg.get("env"))
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                res = await s.call_tool(tool, args)
                return [c.text for c in res.content if hasattr(c, "text")]
