import uuid
from middleware import audit
from datetime import datetime

POLICY = {"list_events": "allow", "read_email": "allow",
          "create_event": "approve", "send_email": "approve", "post_slack": "approve",
          "delete_event": "deny"}

class PendingQueue:
    def __init__(self): self.items = {}

    def add(self, action, params, summary):
        i = uuid.uuid4().hex[:8]
        self.items[i] = {"id": i, "action": action, "params": params, "summary": summary, "status": "pending"}
        audit("queued", id=i, action=action); return self.items[i]
    
    def pending(self): return [x for x in self.items.values() if x["status"] == "pending"]

class Guardrail:
    def __init__(self, hub, queue): self.hub, self.q = hub, queue
    def request(self, action, params, summary=""):
        rule = POLICY.get(action, "deny")         
        if rule == "deny":
            audit("blocked", action=action); return {"status": "blocked", "reason": f"'{action}' is never allowed automatically."}
        if rule == "approve":
            return {"status": "pending", "item": self.q.add(action, params, summary)}
        return {"status": "done", "result": self.hub.call(action, params)}
    
    def approve(self, item_id, overrides=None):
        it = self.q.items.get(item_id)
        if not it or it["status"] != "pending": return {"status": "error", "reason": "not found"}
        params = {**it["params"], **(overrides or {})}
        if it["action"] == "create_event":
            try: ok = datetime.fromisoformat(params["end"]) > datetime.fromisoformat(params["start"])
            except Exception: ok = False
            if not ok:
                return {"status": "error", "reason": "End must be after start (format 2026-10-03T14:00). Fix the fields and approve again."}
        it["params"], it["status"] = params, "approved"
        audit("approved", id=item_id, params=str(params))
        try:
            return {"status": "done", "result": self.hub.call(it["action"], it["params"]), "item": it}
        except Exception as e:
            it["status"] = "pending"          
            audit("error", where="approve", error=str(e))
            return {"status": "error", "reason": f"Failed: {e}"}
        
    def reject(self, item_id):
        it = self.q.items.get(item_id)
        if it: it["status"] = "rejected"; audit("rejected", id=item_id)
        return {"status": "rejected"}
