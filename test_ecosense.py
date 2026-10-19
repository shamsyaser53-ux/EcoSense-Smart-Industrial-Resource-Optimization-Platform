"""Sanity checks: parity with the notebook (2025) and generalization to new data (2026)."""
import pandas as pd
from sklearn.metrics import precision_score, recall_score, f1_score

from ecosense import (add_time_features, analyze, clean_data, detect, load_artifacts)

art = load_artifacts("artifacts.joblib")

for name, path in [("2025 (training data)", "factory_data.csv"), ("2026 (unseen data)", "factory_data_2026.csv")]:
    raw = pd.read_csv(path)
    df = add_time_features(clean_data(raw))
    det = detect(df, art)
    y, p = det["is_anomaly"], det["is_flagged"]
    res = analyze(raw, art)
    print(f"\n=== {name}")
    print(f"hourly  P={precision_score(y, p):.3f} R={recall_score(y, p):.3f} F1={f1_score(y, p):.3f} flagged={int(p.sum())}")
    print(f"events={res['summary']['num_events']} waste_egp={res['summary']['total_waste_egp']:.0f} co2_kg={res['summary']['total_waste_co2_kg']:.0f}")
    print(pd.DataFrame(res["summary"]["by_meter"])[["meter", "events", "waste_qty", "unit", "waste_egp"]].to_string(index=False))
    print(pd.DataFrame(res["recommendations"])[["meter", "solution", "annual_saving_egp", "payback_months"]].round(1).to_string(index=False))
