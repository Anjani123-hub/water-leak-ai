from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)

def test_history_logs_actions():
    c.get("/api/run?scenario=leak"); c.post("/api/teams/T7")
    lid = c.get("/api/state").json()["leaks"]
    h = c.get("/api/history").json()
    assert any(e["action"] == "hypothesis_updated" for e in h["events"]) and h["leaks"]

def test_new_scenarios():
    assert c.get("/api/run?scenario=flow_only").json()["anomalies"]["DMA-B"]["flow_anomaly"]
    assert c.get("/api/run?scenario=pressure_only").json()["anomalies"]["DMA-B"]["pressure_anomaly"]
