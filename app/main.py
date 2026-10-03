from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from . import agents

from fastapi.middleware.cors import CORSMiddleware
app = FastAPI(title="Agentic Water Leak Detection")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/")
def home(): return FileResponse(Path(__file__).parent / "static" / "index.html")

@app.get("/api/run")
def run(scenario: str = "leak"):
    if scenario not in ("normal", "leak", "bad_sensor", "flow_only", "pressure_only"): raise HTTPException(400, "scenario: normal|leak|bad_sensor|flow_only|pressure_only")
    return agents.run(scenario)

@app.post("/api/approve/{leak_id}/{team}")
def approve(leak_id: str, team: str):
    try: return agents.approve(leak_id, team)
    except (KeyError, ValueError) as e: raise HTTPException(400, str(e))

@app.post("/api/repair/{leak_id}")
def repair(leak_id: str):
    try: return agents.post_repair(leak_id)
    except KeyError: raise HTTPException(404, "unknown leak")

@app.get("/api/state")
def state(): return {"leaks": agents.STORE["leaks"], "teams": agents.STORE["teams"]}

import pandas as pd
from fastapi import UploadFile
from fastapi.responses import Response
from .data import today
from . import report

@app.get("/api/reassess")  # TC-07: confidence as more sensor hours arrive
def reassess(scenario: str = "leak"):
    keys = ("leak_id", "zone", "confidence", "confidence_score", "status", "est_loss_m3")
    return [{"hours_of_data": h, "leaks": [{k: l[k] for k in keys} for l in agents.run(scenario, hours=h)["leaks"]]} for h in (3, 4, 5)]

@app.post("/api/upload")  # CSV columns: ts,zone,flow,p_up,p_dn
async def upload(file: UploadFile):
    df = pd.read_csv(file.file, parse_dates=["ts"])
    miss = {"ts", "zone", "flow", "p_up", "p_dn"} - set(df.columns)
    if miss: raise HTTPException(400, f"missing columns: {sorted(miss)}")
    return agents.run("upload", raw=df)

@app.get("/api/sample.csv")
def sample(): return Response(today("leak").to_csv(index=False), media_type="text/csv")

@app.get("/api/report.pdf")
def pdf():
    if not agents.STORE["last"]: agents.run("leak")
    return Response(report.build(agents.STORE["last"]), media_type="application/pdf",
                    headers={"Content-Disposition": "inline; filename=water_report.pdf"})

import re
from fastapi import Query

def _pos(n):
    off = {"A": (.02, -.03), "B": (0, 0), "C": (-.02, .03)}
    if n == "RES": return [16.545, 80.648]
    z, k = n[2], int(n[3])
    return [round(16.5062 + off[z][0] - .008 * (k - 1), 5), round(80.648 + off[z][1] + .010 * (k - 1), 5)]

@app.get("/api/network")  # topology + status colours for the Leaflet map
def network():
    last = agents.STORE["last"] or agents.run("leak")
    sus = {p for l in last["leaks"] for p in re.findall(r"PIPE-\w+", l["suspected_section"])}
    bad = {agents.SENSORS[i["zone"]]["dn"] for i in last["sensor_issues"]}
    pipes = [{"pipe": d["pipe"], "from": _pos(u), "to": _pos(v), "status": "suspected_leak" if d["pipe"] in sus else "normal"}
             for u, v, d in agents.TOPO.edges(data=True)]
    kind = lambda n: "reservoir" if n == "RES" else "upstream pressure sensor" if n.endswith("1") else "downstream pressure sensor" if n.endswith("3") else "junction"
    nodes = [{"id": n, "kind": kind(n), "pos": _pos(n), "status": "sensor_problem" if n in bad else "normal"} for n in agents.TOPO.nodes]
    return {"pipes": pipes, "nodes": nodes}

@app.post("/api/teams/{team_id}")
def add_team(team_id: str, skills: str = Query("acoustic")):
    agents.TEAMS[team_id] = {"skills": skills.split(","), "free": True}
    return agents.TEAMS

from . import db

@app.get("/api/history")  # persisted leaks + audit trail
def history(): return {"leaks": db.leaks(), "events": db.events()}
