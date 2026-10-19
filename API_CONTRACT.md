# EcoSense - Backend / Frontend Contract

## Files the backend needs
`ecosense.py`, `ref_params.py`, `solutions_catalog.csv`, `artifacts.joblib`, `app.py`, `requirements.txt`
(plus `factory_data_2026.csv` for the `/demo` endpoint).

Setup: `pip install -r requirements.txt`, then `uvicorn app:app --reload`.
`artifacts.joblib` is created by `python train.py factory_data.csv artifacts.joblib`.
It must be loaded with the same scikit-learn version it was trained with (see `requirements.txt`).

## Input data (one record per hour)
| field | type | unit |
|---|---|---|
| timestamp | ISO string, hourly | e.g. `2026-01-01 00:00:00` |
| machines_kwh, cooling_kwh, compressed_air_kwh, lighting_kwh, other_kwh | number | kWh in that hour |
| water_m3 | number | m3 |
| fuel_liters | number | liters |
| temp_c | number | outdoor temperature, C |
| production_level | number 0-1 | share of full production |

Extra columns (`total_kwh`, labels) are ignored. Minimum 48 rows; 30+ days recommended
(shorter data returns `meta.warning`). Gaps up to 3 hours are interpolated; negatives are discarded.

## Endpoints
| method | path | body | purpose |
|---|---|---|---|
| GET | `/health` | - | check the service is up |
| GET | `/defaults` | - | default prices for the input boxes (`prices`) and tariff by voltage level |
| GET | `/demo` | optional query: `tariff_egp_per_kwh`, `water_egp_per_m3`, `diesel_egp_per_liter` | analysis of the bundled demo year ("Use Demo Data" button) |
| POST | `/analyze` | JSON `{"records": [...], "prices": {...}}` | analyze uploaded data (`prices` optional) |
| POST | `/analyze-csv` | multipart: file field `file`, optional text field `prices` (JSON string, e.g. `{"tariff_egp_per_kwh": 2.5}`) | same, straight from a CSV file |
| POST | `/what-if` | JSON `{"recommendation": {...}, "saving_pct": 0.1, "unit_price": 3.0}` | recompute one recommendation |

`prices` may override: `tariff_egp_per_kwh`, `water_egp_per_m3`, `diesel_egp_per_liter`,
`grid_emission_kg_per_kwh`, `diesel_emission_kg_per_liter` (positive numbers only).

For `/what-if`, send back one object from `recommendations` exactly as received, plus the new
`saving_pct` (0 to 1) and/or `unit_price`. The response is the same object with updated
`annual_saving_qty`, `annual_saving_egp`, `payback_months`, `annual_co2_kg`.

Errors: `422` = bad input (message in `detail`), `500` = unexpected server error.

## Response of `/demo`, `/analyze`, `/analyze-csv`
```json
{
  "meta": {
    "rows": 8760,
    "start": "2026-01-01T00:00:00",
    "end": "2026-12-31T23:00:00",
    "flagged_hours": 1615,
    "currency": "EGP",
    "prices": {
      "tariff_egp_per_kwh": 2.55,
      "grid_emission_kg_per_kwh": 0.44,
      "diesel_egp_per_liter": 20.5,
      "diesel_emission_kg_per_liter": 2.69,
      "water_egp_per_m3": 4.55,
      "chiller_cop_baseline": 3.2
    },
    "warning": null,
    "disclaimer": "Figures are estimates ..."
  },
  "summary": {
    "total_waste_egp": 85157.16,
    "total_waste_co2_kg": 14476.05,
    "num_events": 56,
    "by_meter": [
      {
        "meter": "cooling_kwh",
        "meter_label": "Cooling",
        "events": 8,
        "waste_qty": 14113.69,
        "unit": "kWh",
        "waste_egp": 35989.92,
        "waste_co2_kg": 6210.02
      }
    ]
  },
  "events": [
    {
      "id": 1,
      "start": "2026-01-01T00:00:00",
      "end": "2026-01-01T02:00:00",
      "hours": 3,
      "meter": "other_kwh",
      "meter_label": "Other loads",
      "waste_qty": 9.09,
      "unit": "kWh",
      "waste_egp": 23.18,
      "waste_co2_kg": 4.0,
      "severity": "low"
    }
  ],
  "recommendations": [
    {
      "meter": "compressed_air_kwh",
      "solution": "Fix compressed-air leaks",
      "saving_pct": 0.15,
      "capex_egp": 60000.0,
      "source": "US DOE Compressed Air Tip Sheet #3 ...",
      "annual_consumption": 686436.79,
      "unit": "kWh",
      "unit_price": 2.55,
      "unit_co2": 0.44,
      "waste_found_egp": 27101.88,
      "annual_saving_qty": 102965.52,
      "annual_saving_egp": 262562.07,
      "payback_months": 2.74,
      "annual_co2_kg": 45304.83
    }
  ],
  "daily": [
    {
      "date": "2026-01-01",
      "total_kwh": 6701.53,
      "water_m3": 50.67,
      "fuel_liters": 84.75,
      "flagged_hours": 3
    }
  ]
}
```

## How the frontend should use it
- **KPI cards**: `summary.total_waste_egp`, `summary.total_waste_co2_kg`, `summary.num_events`.
- **Chart**: `daily` (x = date, y = total_kwh); highlight days with `flagged_hours > 0`, or shade each event from `events[].start` to `events[].end`.
- **Issues table**: `events`, sorted by `waste_egp`; show `severity` as a colored badge (`high` / `medium` / `low`).
- **Recommendations**: `recommendations` (already sorted by shortest payback). `payback_months` can be `null` if the saving is 0.
- **What-If sliders**: call `/what-if` on each slider change, or recompute locally:
  `annual_saving_egp = annual_consumption * saving_pct * unit_price`, `payback_months = capex_egp / (annual_saving_egp / 12)`.
- Always display `meta.disclaimer` and `meta.warning` (if not null) somewhere on the page.

## Notes
- `waste_found_egp` is evidence (detected excess consumption); `annual_saving_egp` is the potential of the solution
  (catalog `saving_pct` applied to the annualized meter consumption). They are different numbers on purpose.
- Edit `solutions_catalog.csv` to change solutions, capex or saving percentages; no retraining is needed.
- Reference prices live in `ref_params.py` and are approximate until verified.
