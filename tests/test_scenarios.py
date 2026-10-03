from app import agents

def test_tc01_normal_no_alert():
    r = agents.run("normal"); assert r["leaks"] == []

def test_tc04_leak_hypothesis_dmab():
    r = agents.run("leak"); l = [x for x in r["leaks"] if x["zone"] == "DMA-B"]
    assert l and l[0]["confidence"] == "High" and "PIPE-B" in l[0]["suspected_section"]

def test_tc06_bad_sensor_flagged():
    r = agents.run("bad_sensor"); assert any(i["issue"] == "impossible pressure" for i in r["sensor_issues"])

def test_tc08_post_repair_and_no_double_assign():
    l = agents.run("leak")["leaks"][0]; agents.approve(l["leak_id"], "T1")
    try: agents.approve(l["leak_id"], "T1"); assert False
    except ValueError: pass
    assert agents.post_repair(l["leak_id"])["after_mnf"] < 120
