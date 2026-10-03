"""Runs TC-01..TC-08 and writes docs/TEST_CASES.md.  Usage: python -m scripts.gen_test_report"""
import os; os.environ.setdefault("WATER_DB", ":memory:")
from app import agents
for t in agents.TEAMS.values(): t["free"] = True
A = lambda r, z="DMA-B": r["anomalies"][z]
def L(r): return [l for l in r["leaks"] if l["zone"] == "DMA-B"]
rows = []
def case(tc, title, scen, exp, fn, hours=5):
    r = agents.run(scen, hours=hours); ok, actual = fn(r)
    rows.append((tc, title, scen, exp, actual, ok, r))
case("TC-01", "Normal flow and pressure", "normal", "No leak alert", lambda r: (r["leaks"] == [], f"{len(r['leaks'])} leak hypotheses"))
case("TC-02", "Flow suddenly increases", "flow_only", "Flow anomaly detected", lambda r: (A(r)["flow_anomaly"], f"flow_anomaly={A(r)['flow_anomaly']}, max z={A(r)['max_z']}"))
case("TC-03", "Downstream pressure drops", "pressure_only", "Pressure anomaly detected", lambda r: (A(r)["pressure_anomaly"], f"pressure drop {A(r)['pressure_drop_bar']} bar"))
case("TC-04", "Flow increase + pressure drop", "leak", "Leak hypothesis generated", lambda r: (bool(L(r)), f"{L(r)[0]['leak_id']} {L(r)[0]['status']} ({L(r)[0]['confidence']})" if L(r) else "none"))
case("TC-05", "Night flow stays high", "flow_only", "Persistent leak indicator", lambda r: (A(r)["mnf_anomaly"], f"min night flow {A(r)['mnf_now']} vs baseline {A(r)['mnf_baseline']} m3/h"))
case("TC-06", "Impossible pressure", "bad_sensor", "Sensor verification requested", lambda r: (any(i["issue"] == "impossible pressure" for i in r["sensor_issues"]), f"{len(r['sensor_issues'])} sensor issue(s), excluded"))
sc = []
for h in (3, 4, 5):
    x = L(agents.run("leak", hours=h)); sc.append((h, x[0]["confidence_score"], x[0]["status"]) if x else (h, 0, "none"))
rows.append(("TC-07", "New evidence arrives", "leak", "Confidence updated as data arrives", "; ".join(f"{h}h: {c} {s}" for h, c, s in sc), sc[-1][1] >= sc[0][1] and sc[-1][1] >= .8, agents.run("leak")))
r = agents.run("leak"); lid = L(r)[0]["leak_id"]; agents.approve(lid, "T1"); pr = agents.post_repair(lid)
rows.append(("TC-08", "Repair completed", "leak", "Before/after compared", f"night flow {pr['before_mnf']} -> {pr['after_mnf']} m3/h; pressure drop {pr['before_pressure_drop_bar']} -> {pr['after_pressure_drop_bar']} bar", pr["after_mnf"] < pr["before_mnf"], r))
out = ["# Test Cases (auto-generated)\n", "Initial network state for all cases: 3 DMAs (A, B, C), 60 days of normal history, RandomForest forecaster, simulated sensors; 00:00-04:00 on 2026-10-03.\n"]
for tc, title, scen, exp, act, ok, r in rows:
    f = r.get("forecast_metrics", {}).get("DMA-B", {})
    out += [f"## {tc} - {title}", f"- **Input scenario:** `{scen}`", f"- **Expected:** {exp}", f"- **Actual:** {act}",
            f"- **Agents involved:** {', '.join(r.get('trace', ['a1..a8']))}", f"- **Forecast model (DMA-B validation):** {f}",
            f"- **Supporting evidence:** {(L(r)[0]['evidence'] if r.get('leaks') and L(r) else 'n/a')}",
            f"- **Final state:** {(L(r)[0]['workflow'] if r.get('leaks') and L(r) else 'no active leak')}", f"- **Result:** {'PASS' if ok else 'FAIL'}\n"]
open("docs/TEST_CASES.md", "w").write("\n".join(out)); print("\n".join(f"{t}: {'PASS' if o else 'FAIL'}" for t, _, _, _, _, o, _ in rows))
