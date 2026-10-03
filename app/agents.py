"""Seven agents + reviewer, orchestrated over a shared workflow state (plain-Python graph;
each agent is a function state->state so it can be wrapped as a LangGraph node later)."""
import numpy as np, pandas as pd, networkx as nx
from sklearn.ensemble import RandomForestRegressor
from .data import history, today
from . import db

TOPO = nx.Graph()  # simple per-zone topology: reservoir -> J1 -> J2 -> J3 via named pipes
for z in "ABC":
    for a, b, p in [("RES", f"J-{z}1", f"PIPE-{z}12"), (f"J-{z}1", f"J-{z}2", f"PIPE-{z}15"),
                    (f"J-{z}2", f"J-{z}3", f"PIPE-{z}18")]:
        TOPO.add_edge(a, b, pipe=p)
SENSORS = {z: {"up": f"J-{z[-1]}1", "dn": f"J-{z[-1]}3"} for z in ["DMA-A", "DMA-B", "DMA-C"]}
TEAMS = {"T1": {"skills": ["acoustic"], "free": True}, "T2": {"skills": ["acoustic", "excavation"], "free": True}}
WEIGHTS = dict(loss=.30, pressure=.20, duration=.15, confidence=.25, criticality=.10)
CRIT = {"DMA-A": .5, "DMA-B": .8, "DMA-C": .5}
STORE = {"leaks": {}, "teams": TEAMS, "counter": 24, "zone_leak": {}, "last": None}

def feats(ts):
    ts = pd.DatetimeIndex(ts)
    return np.c_[ts.hour, ts.dayofweek, np.sin(2*np.pi*ts.hour/24), np.cos(2*np.pi*ts.hour/24)]

# Agent 1 - data monitoring/validation
def a1_validate(s):
    df, issues = s["raw"].copy(), []
    df = df.drop_duplicates(["ts", "zone"])
    for i, r in df.iterrows():
        if r.p_dn < 0 or r.p_up < 0 or r.p_dn > 15:
            issues.append({"zone": r.zone, "ts": str(r.ts), "issue": "impossible pressure", "value": round(r.p_dn, 2),
                           "action": "sensor verification requested; excluded from leak analysis"})
            df.loc[i, ["p_up", "p_dn"]] = np.nan
        if r.flow < 0 or pd.isna(r.flow):
            issues.append({"zone": r.zone, "ts": str(r.ts), "issue": "invalid flow"}); df.loc[i, "flow"] = np.nan
    s["clean"], s["issues"] = df, issues
    return s

# Agent 2 - demand forecasting (RandomForest, 50d train / 10d validation)
def a2_forecast(s):
    h, out, metrics = s["hist"], [], {}
    for z, g in h.groupby("zone"):
        cut = g.ts.max() - pd.Timedelta(days=10)
        tr, va = g[g.ts <= cut], g[g.ts > cut]
        m = RandomForestRegressor(100, random_state=0).fit(feats(tr.ts), tr.flow)
        res = va.flow.values - m.predict(feats(va.ts))
        metrics[z] = {"MAE": round(float(np.abs(res).mean()), 2), "RMSE": round(float(np.sqrt((res**2).mean())), 2),
                      "MAPE_%": round(float((np.abs(res) / va.flow.values).mean() * 100), 2)}
        m.fit(feats(g.ts), g.flow)
        c = s["clean"][s["clean"].zone == z]
        out.append(pd.DataFrame({"ts": c.ts, "zone": z, "forecast": m.predict(feats(c.ts)), "sigma": res.std()}))
    s["forecast"], s["metrics"] = pd.concat(out), metrics
    return s

# Agent 3 - anomaly detection (forecast residual z-score + pressure baseline + minimum night flow)
def a3_anomaly(s):
    h, res = s["hist"], {}
    for z in SENSORS:
        c = s["clean"][s["clean"].zone == z].merge(s["forecast"][s["forecast"].zone == z], on=["ts", "zone"])
        c["z"] = (c.flow - c.forecast) / c.sigma
        hz = h[h.zone == z]
        base_dn = hz.groupby(hz.ts.dt.hour).p_dn.mean()
        drop = (c.ts.dt.hour.map(base_dn) - c.p_dn)
        night = hz[hz.ts.dt.hour.between(1, 4)].groupby(hz.ts.dt.date).flow.min()
        mnf_now, bad = c[c.ts.dt.hour.between(1, 4)].flow.min(), c.z > 3
        up_delta = (c.p_up - c.ts.dt.hour.map(hz.groupby(hz.ts.dt.hour).p_up.mean())).abs().max()
        res[z] = {"max_z": round(float(c.z.max()), 1), "flow_anomaly": int(bad.sum()) >= 2,
                  "anomalous_hours": [str(t) for t in c.ts[bad]],
                  "excess": [round(float(x), 1) for x in (c.flow - c.forecast)[bad]],
                  "pressure_drop_bar": None if drop.isna().all() else round(float(drop.max()), 2),
                  "pressure_anomaly": bool(drop.max() > .5) if drop.notna().any() else False,
                  "upstream_stable": bool(up_delta < .3) if pd.notna(up_delta) else None,
                  "mnf_now": round(float(mnf_now), 1), "mnf_baseline": round(float(night.mean()), 1),
                  "mnf_anomaly": bool(mnf_now > night.mean() + 3 * night.std()),
                  "inlet_mean": round(float(c.flow.mean()), 1), "n": len(c), "forecast_mean": round(float(c.forecast.mean()), 1)}
    s["anom"] = res
    return s

# Agent 4 - leak detection & localization (multi-sensor correlation + topology)
def a4_leak(s):
    s["hyp"] = []
    for z, a in s["anom"].items():
        score = .35*a["flow_anomaly"] + .30*a["pressure_anomaly"] + .25*a["mnf_anomaly"] + .10*bool(a["upstream_stable"] and a["pressure_anomaly"])
        if score < .3: continue
        ev = [t for t, f in [("Flow significantly above forecast demand", a["flow_anomaly"]),
              (f"Downstream pressure decreased ({a['pressure_drop_bar']} bar)", a["pressure_anomaly"]),
              ("Abnormal minimum nighttime flow", a["mnf_anomaly"]),
              ("Upstream pressure comparatively stable", a["upstream_stable"] and a["pressure_anomaly"])] if f]
        con = [t for t, f in [("No flow anomaly", not a["flow_anomaly"]), ("No pressure anomaly", not a["pressure_anomaly"]),
               ("Night flow normal", not a["mnf_anomaly"])] if f]
        sec = None
        if a["pressure_anomaly"] and a["upstream_stable"]:
            path = nx.shortest_path(TOPO, SENSORS[z]["up"], SENSORS[z]["dn"])
            sec = [TOPO[u][v]["pipe"] for u, v in zip(path, path[1:])]
        if z not in STORE["zone_leak"]:
            STORE["counter"] += 1; STORE["zone_leak"][z] = f"LEAK-{STORE['counter']:03d}"
        status = "Field Verification Required" if score >= .8 else "Probable" if score >= .5 else "Possible"
        s["hyp"].append({"leak_id": STORE["zone_leak"][z], "zone": z, "confidence_score": round(score, 2),
            "confidence": "High" if score >= .8 else "Medium" if score >= .5 else "Low", "status": status,
            "suspected_section": f"{sec[0]} to {sec[-1]} (suspected, NOT a confirmed location)" if sec else "Zone-level only",
            "evidence": ev, "contradicting": con, "est_start": (a["anomalous_hours"] or ["unknown"])[0],
            "verification": "Field inspection / acoustic confirmation recommended"})
    return s

# Agent 5 - water balance & loss (deterministic; simplified, not full IWA NRW)
def a5_balance(s):
    s["balance"], per_leak = {}, {}
    for z, a in s["anom"].items():
        inflow, cons = a["inlet_mean"] * a["n"], a["forecast_mean"] * a["n"]   # forecast = expected authorised use
        s["balance"][z] = {"inflow_m3": round(inflow, 1), "expected_consumption_m3": round(cons, 1),
            "unexplained_m3": round(inflow - cons, 1), "pct_difference": round((inflow - cons) / inflow * 100, 1),
            "note": "Simplified. Full NRW needs unbilled use, apparent losses, meter error."}
    for h in s["hyp"]:
        ex = s["anom"][h["zone"]]["excess"]
        h["est_loss_m3"] = round(sum(ex), 1); h["est_rate_m3h"] = round(float(np.mean(ex)), 1) if ex else 0
        h["loss_assumption"] = "Excess over ML forecast during anomalous hours only; hourly flow treated as constant."
    return s

# Agent 6 - maintenance planning (transparent weighted score, no double assignment)
def a6_maintenance(s):
    s["plans"] = []
    for h in sorted(s["hyp"], key=lambda x: -x["confidence_score"]):
        a = s["anom"][h["zone"]]
        f = dict(loss=min(h["est_rate_m3h"] / 100, 1), pressure=min((a["pressure_drop_bar"] or 0) / 2, 1),
                 duration=min(len(a["anomalous_hours"]) / 6, 1), confidence=h["confidence_score"], criticality=CRIT[h["zone"]])
        score = round(100 * sum(WEIGHTS[k] * v for k, v in f.items()), 1)
        team = next((t for t, v in TEAMS.items() if v["free"] and "acoustic" in v["skills"]), None)
        s["plans"].append({"leak_id": h["leak_id"], "zone": h["zone"], "priority_score": score,
            "factors": {k: round(v, 2) for k, v in f.items()}, "inspection": "Acoustic survey", "suggested_team": team})
    return s

# Agent 8 - reviewer/critic
def a8_review(s):
    s["review"] = []
    for h in s["hyp"]:
        if h["confidence"] == "High" and len(h["evidence"]) < 3: s["review"].append(f"{h['leak_id']}: high confidence with <3 evidence items")
        if "confirmed" in h["suspected_section"].lower() and "NOT" not in h["suspected_section"]: s["review"].append(f"{h['leak_id']}: unsupported confirmed location")
    if s["issues"]: s["review"].append(f"{len(s['issues'])} sensor issue(s) excluded from analysis")
    s["review"] = s["review"] or ["No conflicts found"]
    return s

# Agent 7 - coordinator: recommendation -> operator approval (never actuates infrastructure)
def a7_coordinate(s):
    for h in s["hyp"]:
        p = next(p for p in s["plans"] if p["leak_id"] == h["leak_id"])
        old = STORE["leaks"].get(h["leak_id"])
        h.update(plan=p, workflow=old["workflow"] if old else "PENDING_OPERATOR_APPROVAL",
                 history=(old or {}).get("history", []) + [{"hours_of_data": s["n_hours"], "score": h["confidence_score"], "status": h["status"]}])
        h["before_mnf"] = s["anom"][h["zone"]]["mnf_now"]; h["before_pressure_drop_bar"] = s["anom"][h["zone"]]["pressure_drop_bar"]
        STORE["leaks"][h["leak_id"]] = h; db.save_leak(h); db.log(h["leak_id"], "hypothesis_updated", h["history"][-1])
    s["summary"] = [f"{h['leak_id']} {h['zone']} {h['status']} priority {h['plan']['priority_score']} - awaiting approval" for h in s["hyp"]] \
        or ["No leak hypotheses. Network normal."]
    return s

PIPELINE = [a1_validate, a2_forecast, a3_anomaly, a4_leak, a5_balance, a6_maintenance, a8_review, a7_coordinate]

_HIST = None
def run(scenario="normal", raw=None, hours=5):
    global _HIST
    _HIST = _HIST if _HIST is not None else history()
    raw = today(scenario) if raw is None else raw
    if hours < 5: raw = raw[raw.ts < raw.ts.min() + pd.Timedelta(hours=hours)]
    s, trace = {"hist": _HIST, "raw": raw, "n_hours": int(raw.ts.nunique())}, []
    for fn in PIPELINE:
        s = fn(s); trace.append(fn.__name__)
    obs = s["clean"].merge(s["forecast"], on=["ts", "zone"])
    series = {z: {"t": g.ts.dt.strftime("%H:%M").tolist(), "actual": g.flow.round(1).tolist(), "forecast": g.forecast.round(1).tolist()}
              for z, g in obs.groupby("zone")}
    STORE["last"] = res = {"scenario": scenario, "trace": trace, "sensor_issues": s["issues"], "forecast_metrics": s["metrics"],
            "anomalies": s["anom"], "leaks": s["hyp"], "water_balance": s["balance"], "review": s["review"],
            "summary": s["summary"], "series": series}
    return res

def approve(leak_id, team):
    h = STORE["leaks"][leak_id]
    if not TEAMS[team]["free"]: raise ValueError(f"{team} already assigned")
    TEAMS[team]["free"] = False; h["workflow"] = "APPROVED_TEAM_" + team; h["status"] = "Field Verification Required"
    db.save_leak(h); db.log(leak_id, "inspection_approved", team)
    return h

def post_repair(leak_id):  # compares before/after (after = simulated normal conditions)
    h = STORE["leaks"][leak_id]; a = run("normal")["anomalies"][h["zone"]]
    before = {"night_flow": h["_before"] if "_before" in h else None}
    h["workflow"] = "REPAIR_RECORDED_PENDING_HUMAN_VERIFICATION"
    res = {"leak_id": leak_id, "before_mnf": h.get("before_mnf"), "before_pressure_drop_bar": h.get("before_pressure_drop_bar"), "after_mnf": a["mnf_now"], "after_pressure_drop_bar": a["pressure_drop_bar"],
            "note": "Observed improvement only; final repair verification belongs to authorised personnel."}
    db.save_leak(h); db.log(leak_id, "repair_recorded", res)
    return res
