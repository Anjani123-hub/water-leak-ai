import io
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

def build(r):
    b = io.BytesIO(); c = canvas.Canvas(b, pagesize=A4); st = {"y": 800}
    def line(t, sz=10):
        if st["y"] < 60: c.showPage(); st["y"] = 800
        c.setFont("Helvetica", sz); c.drawString(40, st["y"], str(t)[:105]); st["y"] -= sz + 5
    line("Water Network Operations Report", 16); line(f"Scenario: {r['scenario']}  |  Data window: 2026-10-03 00:00-04:00"); line("")
    line("Summary", 12); [line(x) for x in r["summary"]]; line("")
    line("Demand forecast quality (Random Forest, 10-day validation)", 12)
    for z, m in r["forecast_metrics"].items(): line(f"{z}: {m}")
    line(""); line("Water balance (simplified, not full IWA NRW)", 12)
    for z, w in r["water_balance"].items(): line(f"{z}: inflow {w['inflow_m3']} m3, expected {w['expected_consumption_m3']} m3, unexplained {w['unexplained_m3']} m3 ({w['pct_difference']}%)")
    line(""); line("Suspected leaks (hypotheses, not confirmed)", 12)
    for l in r["leaks"]:
        line(f"{l['leak_id']} {l['zone']} - {l['status']} ({l['confidence']}, {l['confidence_score']})", 11)
        line(f"  Section: {l['suspected_section']}")
        for e in l["evidence"]: line(f"  + {e}")
        for e in l["contradicting"]: line(f"  - {e}")
        line(f"  Est. loss {l['est_loss_m3']} m3 | Assumption: {l['loss_assumption']}")
        line(f"  Workflow: {l['workflow']} | Priority {l['plan']['priority_score']} | Team {l['plan']['suggested_team']}")
    if not r["leaks"]: line("None")
    line(""); line("Sensor issues", 12)
    [line(f"{i['zone']} {i['ts']}: {i['issue']} ({i['value']})") for i in r["sensor_issues"]] or line("None")
    line(""); line("Reviewer", 12); [line(x) for x in r["review"]]
    line(""); line("Decision-support only. No physical infrastructure is operated; final verification by authorised staff.", 9)
    c.save(); return b.getvalue()
