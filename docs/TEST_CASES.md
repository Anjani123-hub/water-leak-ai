# Test Cases (auto-generated)

Initial network state for all cases: 3 DMAs (A, B, C), 60 days of normal history, RandomForest forecaster, simulated sensors; 00:00-04:00 on 2026-10-03.

## TC-01 - Normal flow and pressure
- **Input scenario:** `normal`
- **Expected:** No leak alert
- **Actual:** 0 leak hypotheses
- **Agents involved:** a1_validate, a2_forecast, a3_anomaly, a4_leak, a5_balance, a6_maintenance, a8_review, a7_coordinate
- **Forecast model (DMA-B validation):** {'MAE': 4.21, 'RMSE': 5.66, 'MAPE_%': 1.71}
- **Supporting evidence:** n/a
- **Final state:** no active leak
- **Result:** PASS

## TC-02 - Flow suddenly increases
- **Input scenario:** `flow_only`
- **Expected:** Flow anomaly detected
- **Actual:** flow_anomaly=True, max z=10.0
- **Agents involved:** a1_validate, a2_forecast, a3_anomaly, a4_leak, a5_balance, a6_maintenance, a8_review, a7_coordinate
- **Forecast model (DMA-B validation):** {'MAE': 4.21, 'RMSE': 5.66, 'MAPE_%': 1.71}
- **Supporting evidence:** ['Flow significantly above forecast demand', 'Abnormal minimum nighttime flow']
- **Final state:** PENDING_OPERATOR_APPROVAL
- **Result:** PASS

## TC-03 - Downstream pressure drops
- **Input scenario:** `pressure_only`
- **Expected:** Pressure anomaly detected
- **Actual:** pressure drop 1.5 bar
- **Agents involved:** a1_validate, a2_forecast, a3_anomaly, a4_leak, a5_balance, a6_maintenance, a8_review, a7_coordinate
- **Forecast model (DMA-B validation):** {'MAE': 4.21, 'RMSE': 5.66, 'MAPE_%': 1.71}
- **Supporting evidence:** ['Downstream pressure decreased (1.5 bar)', 'Upstream pressure comparatively stable']
- **Final state:** PENDING_OPERATOR_APPROVAL
- **Result:** PASS

## TC-04 - Flow increase + pressure drop
- **Input scenario:** `leak`
- **Expected:** Leak hypothesis generated
- **Actual:** LEAK-025 Field Verification Required (High)
- **Agents involved:** a1_validate, a2_forecast, a3_anomaly, a4_leak, a5_balance, a6_maintenance, a8_review, a7_coordinate
- **Forecast model (DMA-B validation):** {'MAE': 4.21, 'RMSE': 5.66, 'MAPE_%': 1.71}
- **Supporting evidence:** ['Flow significantly above forecast demand', 'Downstream pressure decreased (1.39 bar)', 'Abnormal minimum nighttime flow', 'Upstream pressure comparatively stable']
- **Final state:** PENDING_OPERATOR_APPROVAL
- **Result:** PASS

## TC-05 - Night flow stays high
- **Input scenario:** `flow_only`
- **Expected:** Persistent leak indicator
- **Actual:** min night flow 119.4 vs baseline 94.7 m3/h
- **Agents involved:** a1_validate, a2_forecast, a3_anomaly, a4_leak, a5_balance, a6_maintenance, a8_review, a7_coordinate
- **Forecast model (DMA-B validation):** {'MAE': 4.21, 'RMSE': 5.66, 'MAPE_%': 1.71}
- **Supporting evidence:** ['Flow significantly above forecast demand', 'Abnormal minimum nighttime flow']
- **Final state:** PENDING_OPERATOR_APPROVAL
- **Result:** PASS

## TC-06 - Impossible pressure
- **Input scenario:** `bad_sensor`
- **Expected:** Sensor verification requested
- **Actual:** 1 sensor issue(s), excluded
- **Agents involved:** a1_validate, a2_forecast, a3_anomaly, a4_leak, a5_balance, a6_maintenance, a8_review, a7_coordinate
- **Forecast model (DMA-B validation):** {'MAE': 4.21, 'RMSE': 5.66, 'MAPE_%': 1.71}
- **Supporting evidence:** n/a
- **Final state:** no active leak
- **Result:** PASS

## TC-07 - New evidence arrives
- **Input scenario:** `leak`
- **Expected:** Confidence updated as data arrives
- **Actual:** 3h: 0.65 Probable; 4h: 1.0 Field Verification Required; 5h: 1.0 Field Verification Required
- **Agents involved:** a1_validate, a2_forecast, a3_anomaly, a4_leak, a5_balance, a6_maintenance, a8_review, a7_coordinate
- **Forecast model (DMA-B validation):** {'MAE': 4.21, 'RMSE': 5.66, 'MAPE_%': 1.71}
- **Supporting evidence:** ['Flow significantly above forecast demand', 'Downstream pressure decreased (1.39 bar)', 'Abnormal minimum nighttime flow', 'Upstream pressure comparatively stable']
- **Final state:** PENDING_OPERATOR_APPROVAL
- **Result:** PASS

## TC-08 - Repair completed
- **Input scenario:** `leak`
- **Expected:** Before/after compared
- **Actual:** night flow 119.4 -> 96.3 m3/h; pressure drop 1.39 -> 0.1 bar
- **Agents involved:** a1_validate, a2_forecast, a3_anomaly, a4_leak, a5_balance, a6_maintenance, a8_review, a7_coordinate
- **Forecast model (DMA-B validation):** {'MAE': 4.21, 'RMSE': 5.66, 'MAPE_%': 1.71}
- **Supporting evidence:** ['Flow significantly above forecast demand', 'Downstream pressure decreased (1.39 bar)', 'Abnormal minimum nighttime flow', 'Upstream pressure comparatively stable']
- **Final state:** REPAIR_RECORDED_PENDING_HUMAN_VERIFICATION
- **Result:** PASS
