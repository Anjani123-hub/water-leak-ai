"""Synthetic sensor data (Agent-1 input). Zones: base daytime flow m3/h, base pressure bar."""
import numpy as np, pandas as pd
ZONES = {"DMA-A": (400, 4.2), "DMA-B": (390, 4.1), "DMA-C": (340, 4.0)}
LEAK_FROM = pd.Timestamp("2026-10-03 02:00")

def prof(h):  # daily demand shape: ~0.24 at 03:00, 1.0 at 15:00
    return 0.62 + 0.38 * np.sin(2 * np.pi * (h - 9) / 24)

def make(start, hours, seed, scenario="normal"):
    rng, rows = np.random.default_rng(seed), []
    for z, (base, p0) in ZONES.items():
        for t in pd.date_range(start, periods=hours, freq="h"):
            f = prof(t.hour) * (1.05 if t.dayofweek >= 5 else 1.0)
            flow = base * f * (1 + rng.normal(0, .02))
            up = p0 - .2 * f + rng.normal(0, .03)
            dn = up - .1 + rng.normal(0, .03)
            if scenario in ("leak", "flow_only", "pressure_only") and z == "DMA-B" and t >= LEAK_FROM:
                if scenario != "pressure_only": flow += 55 + rng.normal(0, 3)
                if scenario != "flow_only": dn -= 1.4
            if scenario == "bad_sensor" and z == "DMA-C" and t.hour == 4:
                dn = -3.0
            rows.append((t, z, flow, up, dn))
    return pd.DataFrame(rows, columns=["ts", "zone", "flow", "p_up", "p_dn"])

def history():  # 60 days of normal behaviour
    return make("2026-08-03 00:00", 24 * 60, 1)

def today(scenario):  # 00:00-04:00 on 2026-10-03
    return make("2026-10-03 00:00", 5, 2, scenario)
