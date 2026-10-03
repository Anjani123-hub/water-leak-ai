from fastapi.testclient import TestClient
from app.main import app
c = TestClient(app)

def test_tc07_reassessment_confidence_rises():
    st = c.get("/api/reassess").json()
    sc = [x["leaks"][0]["confidence_score"] for x in st if x["leaks"]]
    assert len(sc) >= 2 and sc[-1] >= sc[0] and sc[-1] >= .8

def test_pdf_report():
    assert c.get("/api/report.pdf").content[:4] == b"%PDF"

def test_csv_upload_roundtrip():
    r = c.post("/api/upload", files={"file": ("s.csv", c.get("/api/sample.csv").content)}).json()
    assert any(l["zone"] == "DMA-B" for l in r["leaks"])
