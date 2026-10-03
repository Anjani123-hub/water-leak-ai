"""SQLite persistence (leaks + audit trail). Swap for PostgreSQL in production."""
import os, json, sqlite3, datetime as dt
_c = sqlite3.connect(os.environ.get("WATER_DB", "water.db"), check_same_thread=False)
_c.execute("create table if not exists leaks(leak_id text primary key, zone text, status text, workflow text, data text)")
_c.execute("create table if not exists events(id integer primary key autoincrement, ts text, leak_id text, action text, detail text)")

def save_leak(h):
    _c.execute("insert or replace into leaks values(?,?,?,?,?)", (h["leak_id"], h["zone"], h["status"], h["workflow"], json.dumps(h, default=str)))
    _c.commit()

def log(leak_id, action, detail=""):
    _c.execute("insert into events(ts,leak_id,action,detail) values(?,?,?,?)", (dt.datetime.now().isoformat(timespec="seconds"), leak_id, action, json.dumps(detail, default=str)))
    _c.commit()

def events(): return [dict(zip(("id", "ts", "leak_id", "action", "detail"), r)) for r in _c.execute("select * from events order by id desc limit 50")]
def leaks(): return [dict(zip(("leak_id", "zone", "status", "workflow"), r)) for r in _c.execute("select leak_id,zone,status,workflow from leaks")]
