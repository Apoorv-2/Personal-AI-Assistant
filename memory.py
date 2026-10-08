import sqlite3, json
from collections import defaultdict, deque
from config import DB_PATH

class ShortTermMemory:
    def __init__(self, size=8):
        self.s = defaultdict(lambda: deque(maxlen=size))
        self.ctx = defaultdict(dict)         

    def add(self, sid, role, text): self.s[sid].append({"role": role, "content": text})
    
    def history(self, sid): return list(self.s[sid])

class LongTermMemory:
    def __init__(self):
        self.db = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.db.execute("CREATE TABLE IF NOT EXISTS contacts(name TEXT PRIMARY KEY, slots TEXT, notes TEXT)")
    
    def get_slots(self, name):
        r = self.db.execute("SELECT slots FROM contacts WHERE name=?", (name.lower(),)).fetchone()
        return json.loads(r[0]) if r else {}
    
    def record_meeting(self, name, hour):
        """Count which hours each contact actually accepts; most frequent = preferred."""
        slots = self.get_slots(name); slots[str(hour)] = slots.get(str(hour), 0) + 1
        self.db.execute("INSERT OR REPLACE INTO contacts VALUES(?,?,COALESCE((SELECT notes FROM contacts WHERE name=?),''))",
                        (name.lower(), json.dumps(slots), name.lower()))
        self.db.commit()

    def preferred_hours(self, names):
        score = defaultdict(int)
        for n in names:
            for h, c in self.get_slots(n).items(): score[int(h)] += c
        return [h for h, _ in sorted(score.items(), key=lambda x: -x[1])]
