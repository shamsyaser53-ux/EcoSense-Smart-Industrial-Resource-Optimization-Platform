# EcoSense

**Finds energy, water and fuel waste in factories, estimates what it costs, and recommends fixes with payback time.**

Built for a 3-day hackathon. The ML part uses scikit-learn only.

## What it does
1. Takes hourly factory data (5 electricity sub-meters, water, fuel, temperature, production level).
2. Learns what each meter *should* consume given production, temperature and time of day.
3. Flags hours that are abnormal, finds the responsible meter, and merges them into events (for example "compressed-air leak, 10-24 March").
4. Converts the excess consumption to EGP and CO2 using Egyptian tariffs.
5. Recommends solutions from `solutions_catalog.csv` with yearly saving and payback, plus a What-If simulator.

## How the detection works
| Stage | Idea |
|---|---|
| Expected-consumption models | One small gradient-boosting model per meter predicts normal use from hour, weekday, temperature and production |
| Residuals | Actual minus expected, with 6h and 48h rolling means so sustained problems stand out from noise |
| Detector | `IsolationForest` on the residual features, threshold set from the expected anomaly rate (15%) |
| Waste estimate | Baselines are refit on healthy hours only, then positive residuals are summed per event |

The notebook `EcoSense_Notebook.ipynb` shows every step, including the feature-engineering experiments (A to E).

## Quick start
Python 3.11+ is recommended.

```bash
pip install -r requirements.txt
python train.py factory_data.csv artifacts.joblib   # optional: artifacts.joblib is already included
uvicorn app:app --reload
```
Then open http://127.0.0.1:8000/docs to try the API (`/demo` analyzes the bundled 2026 data).
If you get a scikit-learn version warning, run `train.py` again to rebuild `artifacts.joblib`.

The backend/frontend contract is in [API_CONTRACT.md](API_CONTRACT.md).

## Results (synthetic data)
Data is **synthetic**: a generated factory year with 6 injected anomaly types (about 15% of hours). See `generate_data.py`.

| | Precision | Recall | F1 |
|---|---|---|---|
| Hourly detection, 2025 (training year) | 0.85 | 0.86 | 0.86 |
| Hourly detection, 2026 (new data, different seed) | 0.77 | 0.93 | 0.84 |

- Large, sustained problems (air leak, chiller degradation, water leak, lights left on, idle machines) were all detected; 14 of 21 short equipment spikes were.
- Event-level precision is about 0.66: some detected events are false alarms.
- Waste estimate vs injected ground truth: air leak 99%, water leak 93%, lights 57% (under-estimated).
- Waste found on the 2026 data: about 85,000 EGP over the year.

## Reference values
Prices and emission factors are in `ref_params.py`, each with its source (EgyptERA tariff April 2026, Ministry of Petroleum diesel price, EPA diesel factor, Ember grid factor).
Items marked VERIFY there (diesel, water) should be re-checked before use. Capex values in `solutions_catalog.csv` are placeholders until real supplier quotes are added.

## Limitations
- Synthetic data only; real factories need real sub-metered data and a calibration period.
- Savings percentages come from published studies and are indicative, not guaranteed.
- Detection assumes about 15% abnormal hours; this is a tunable setting.

## Files
| File | Purpose |
|---|---|
| `ecosense.py` | Core library: cleaning, features, detection, waste, recommendations |
| `app.py` | FastAPI service |
| `train.py` | Trains models and saves `artifacts.joblib` |
| `artifacts.joblib` | Trained models |
| `ref_params.py` | Prices and emission factors with sources |
| `solutions_catalog.csv` | Solutions, saving percentages and capex |
| `generate_data.py` | Synthetic data generator |
| `factory_data.csv`, `factory_data_2026.csv` | Training data and unseen demo data |
| `test_ecosense.py` | Sanity checks on both datasets |
| `EcoSense_Notebook.ipynb` | Step-by-step exploration and experiments |
