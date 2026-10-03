from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)

def test_network_map_marks_suspected_pipes():
    c.get("/api/run?scenario=leak"); n = c.get("/api/network").json()
    assert any(p["status"] == "suspected_leak" for p in n["pipes"]) and len(n["nodes"]) >= 10

def test_bad_sensor_node_marked():
    c.get("/api/run?scenario=bad_sensor"); n = c.get("/api/network").json()
    assert any(x["status"] == "sensor_problem" for x in n["nodes"])

def test_add_team():
    assert "T9" in c.post("/api/teams/T9?skills=acoustic,excavation").json()
