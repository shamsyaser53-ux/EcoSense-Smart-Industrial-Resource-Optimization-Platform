"""EcoSense core: train once, then analyze any new hourly factory data.

Usage:
    artifacts = fit(pd.read_csv("factory_data.csv"))
    save_artifacts(artifacts, "artifacts.joblib")
    ...
    result = analyze(new_df, load_artifacts("artifacts.joblib"))   # JSON-ready dict
"""
import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingRegressor, IsolationForest

from ref_params import REF

logger = logging.getLogger("ecosense")

# ---------------------------------------------------------------- constants
SEED = 42
TIME_COL = "timestamp"
METER_COLS = ["machines_kwh", "cooling_kwh", "compressed_air_kwh", "lighting_kwh", "other_kwh"]
DEV_COLS = METER_COLS + ["water_m3", "fuel_liters"]  # columns we model and analyze
SENSOR_COLS = DEV_COLS + ["temp_c", "production_level"]
REQUIRED_COLS = [TIME_COL] + SENSOR_COLS  # labels (is_anomaly...) are optional
LABEL_COLS = ["is_anomaly", "anomaly_type"]

RES_INPUTS = ["hour", "dow", "temp_c", "production_level"]
RES_FEATURES = [f"{c}_res" for c in DEV_COLS]
ROLL_WINDOWS = (6, 48)
RES_ROLL_FEATURES = [f"{c}_roll{w}" for c in RES_FEATURES for w in ROLL_WINDOWS]
DETECT_FEATURES = RES_FEATURES + RES_ROLL_FEATURES + ["hour_sin", "hour_cos"]
RES6_COLS = [f"{c}_res_roll6" for c in DEV_COLS]

ANOMALY_RATE = 0.15  # assumed share of abnormal hours; sets the detection threshold
MIN_ROWS = 48  # at least two days of data
MIN_EVENT_HOURS = 3
MAX_EVENT_GAP_HOURS = 3
MIN_WASTE_EGP_FOR_REC = 500  # do not recommend capex for tiny waste
HOURS_PER_YEAR = 8760
CATALOG_PATH = Path(__file__).with_name("solutions_catalog.csv")

METER_LABELS = {"machines_kwh": "Machines", "cooling_kwh": "Cooling", "compressed_air_kwh": "Compressed air",
                "lighting_kwh": "Lighting", "other_kwh": "Other loads", "water_m3": "Water",
                "fuel_liters": "Fuel"}
DISCLAIMER = ("Figures are estimates based on the supplied data and reference prices. "
              "Capex and saving percentages are indicative and need real quotes before any investment decision.")


# ------------------------------------------------------------------ cleaning
def clean_data(df: pd.DataFrame, max_gap_hours: int = 3) -> pd.DataFrame:
    """Validate, sort, drop duplicates, null impossible values, fill short gaps."""
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df = df.copy()
    df[TIME_COL] = pd.to_datetime(df[TIME_COL], errors="coerce")
    df[SENSOR_COLS] = df[SENSOR_COLS].apply(pd.to_numeric, errors="coerce")
    df = df.dropna(subset=[TIME_COL]).sort_values(TIME_COL).drop_duplicates(subset=TIME_COL)

    non_negative = DEV_COLS
    df[non_negative] = df[non_negative].mask(df[non_negative] < 0)

    df = df.set_index(TIME_COL).asfreq("h")  # complete hourly index exposes gaps
    df[SENSOR_COLS] = df[SENSOR_COLS].interpolate(method="time", limit=max_gap_hours)
    if "is_anomaly" in df.columns:
        df["is_anomaly"] = df["is_anomaly"].fillna(0).astype(int)
    if "anomaly_type" in df.columns:
        df["anomaly_type"] = df["anomaly_type"].fillna("normal").replace("", "normal")
    df = df.dropna(subset=SENSOR_COLS).reset_index()
    df["total_kwh"] = df[METER_COLS].sum(axis=1)

    if len(df) < MIN_ROWS:
        raise ValueError(f"Not enough valid hourly rows: {len(df)} (need at least {MIN_ROWS})")
    return df


# ---------------------------------------------------------------- features
def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    """Hour (cyclic) and day-of-week."""
    out = df.copy()
    out["hour"] = out[TIME_COL].dt.hour
    out["dow"] = out[TIME_COL].dt.dayofweek
    out["hour_sin"] = np.sin(2 * np.pi * out["hour"] / 24)
    out["hour_cos"] = np.cos(2 * np.pi * out["hour"] / 24)
    return out


def fit_baseline_models(df: pd.DataFrame) -> dict:
    """One expected-consumption model per column. Kept small so it generalizes to unseen data."""
    return {c: HistGradientBoostingRegressor(max_iter=50, min_samples_leaf=100, max_depth=4,
                                             random_state=SEED).fit(df[RES_INPUTS], df[c])
            for c in DEV_COLS}


def add_residual_features(df: pd.DataFrame, models: dict) -> pd.DataFrame:
    """Actual minus expected consumption."""
    out = df.copy()
    for c, model in models.items():
        out[f"{c}_res"] = out[c] - model.predict(out[RES_INPUTS])
    return out


def add_residual_rolling(df: pd.DataFrame, windows=ROLL_WINDOWS) -> pd.DataFrame:
    """Trailing mean of each residual (backward-looking only)."""
    out = df.copy()
    for c in RES_FEATURES:
        for w in windows:
            out[f"{c}_roll{w}"] = out[c].rolling(w, min_periods=1).mean()
    return out


def _residual_frame(df: pd.DataFrame, models: dict) -> pd.DataFrame:
    return add_residual_rolling(add_residual_features(df, models))


# ------------------------------------------------------------------ training
def fit(raw: pd.DataFrame, rate: float = ANOMALY_RATE) -> dict:
    """Train everything on historical data. Returns a dict ready for joblib."""
    df = add_time_features(clean_data(raw))
    models = fit_baseline_models(df)
    feat = _residual_frame(df, models)

    detector = IsolationForest(n_estimators=300, random_state=SEED).fit(feat[DETECT_FEATURES])
    scores = -detector.score_samples(feat[DETECT_FEATURES])
    threshold = float(np.quantile(scores, 1 - rate))

    # Second pass: expected-consumption models on healthy (unflagged) hours only
    clean_models = fit_baseline_models(df[scores <= threshold])

    logger.info("Trained on %d rows, threshold=%.4f", len(df), threshold)
    return {"baseline_models": models, "clean_models": clean_models, "detector": detector,
            "threshold": threshold, "res_scale": feat[RES6_COLS].std(),
            "trained_rows": len(df), "sklearn_version": sklearn.__version__}


def save_artifacts(artifacts: dict, path) -> None:
    joblib.dump(artifacts, path)
    logger.info("Saved artifacts to %s", path)


def load_artifacts(path) -> dict:
    artifacts = joblib.load(path)
    if artifacts.get("sklearn_version") != sklearn.__version__:
        logger.warning("Artifacts trained with scikit-learn %s, running %s",
                       artifacts.get("sklearn_version"), sklearn.__version__)
    return artifacts


# ----------------------------------------------------------------- detection
def detect(df: pd.DataFrame, artifacts: dict) -> pd.DataFrame:
    """Score every hour, flag abnormal ones, and find the responsible meter."""
    out = _residual_frame(df, artifacts["baseline_models"])
    out["score"] = -artifacts["detector"].score_samples(out[DETECT_FEATURES])
    out["is_flagged"] = out["score"] > artifacts["threshold"]
    scaled = out[RES6_COLS] / artifacts["res_scale"]
    out["affected"] = scaled.idxmax(axis=1).str.replace("_res_roll6", "", regex=False)
    return out


def group_events(df: pd.DataFrame, max_gap_hours: int = MAX_EVENT_GAP_HOURS,
                 min_hours: int = MIN_EVENT_HOURS) -> pd.DataFrame:
    """Merge nearby flagged hours into events."""
    cols = ["start", "end", "hours", "meter", "mean_score"]
    flagged = df[df["is_flagged"]]
    if flagged.empty:
        return pd.DataFrame(columns=cols)
    new_event = flagged[TIME_COL].diff() > pd.Timedelta(hours=max_gap_hours)
    events = flagged.groupby(new_event.cumsum()).agg(
        start=(TIME_COL, "min"), end=(TIME_COL, "max"), hours=(TIME_COL, "size"),
        meter=("affected", lambda s: s.mode().iat[0]), mean_score=("score", "mean"))
    return events[events["hours"] >= min_hours].reset_index(drop=True)


# ------------------------------------------------------------ waste (EGP/CO2)
def unit_maps(prices: dict) -> tuple:
    """Price, CO2 factor and unit name per meter."""
    price = {m: prices["tariff_egp_per_kwh"] for m in METER_COLS}
    price.update(water_m3=prices["water_egp_per_m3"], fuel_liters=prices["diesel_egp_per_liter"])
    co2 = {m: prices["grid_emission_kg_per_kwh"] for m in METER_COLS}
    co2.update(water_m3=0.0, fuel_liters=prices["diesel_emission_kg_per_liter"])
    unit = {m: "kWh" for m in METER_COLS}
    unit.update(water_m3="m3", fuel_liters="liter")
    return price, co2, unit


def estimate_waste(df: pd.DataFrame, events: pd.DataFrame, prices: dict) -> pd.DataFrame:
    """Add waste quantity, cost (EGP) and CO2 (kg) to each event. df holds the clean residuals."""
    price, co2, unit = unit_maps(prices)
    out = events.copy()
    qty = []
    for _, ev in out.iterrows():
        span = df[(df[TIME_COL] >= ev["start"]) & (df[TIME_COL] <= ev["end"])]
        qty.append(span[f"{ev['meter']}_res"].clip(lower=0).sum())  # excess only
    out["unit"] = out["meter"].map(unit)
    out["waste_qty"] = qty
    out["waste_egp"] = out["waste_qty"] * out["meter"].map(price)
    out["waste_co2_kg"] = out["waste_qty"] * out["meter"].map(co2)
    return out


# ------------------------------------------------- recommendations + what-if
def solution_economics(annual_qty: float, saving_pct: float, capex: float,
                       unit_price: float, unit_co2: float) -> dict:
    """Yearly saving, payback and CO2 for one solution. Used by recommend() and what_if()."""
    saving_qty = annual_qty * saving_pct
    saving_egp = saving_qty * unit_price
    payback = capex / (saving_egp / 12) if saving_egp > 0 else None
    return {"annual_saving_qty": saving_qty, "annual_saving_egp": saving_egp,
            "payback_months": payback, "annual_co2_kg": saving_qty * unit_co2}


def load_catalog(path=CATALOG_PATH) -> pd.DataFrame:
    catalog = pd.read_csv(path)
    needed = {"solution", "target_meter", "saving_pct", "capex_egp", "source"}
    if not needed.issubset(catalog.columns):
        raise ValueError(f"Catalog must have columns {sorted(needed)}")
    return catalog


def recommend(df: pd.DataFrame, events: pd.DataFrame, catalog: pd.DataFrame, prices: dict) -> list:
    """For each meter with enough detected waste, list matching catalog solutions (best payback first)."""
    price, co2, unit = unit_maps(prices)
    recs = []
    for meter, ev in events.groupby("meter"):
        if ev["waste_egp"].sum() < MIN_WASTE_EGP_FOR_REC:
            continue
        annual_qty = float(df[meter].sum() * HOURS_PER_YEAR / len(df))  # annualized consumption
        for _, s in catalog[catalog["target_meter"] == meter].iterrows():
            eco = solution_economics(annual_qty, s["saving_pct"], s["capex_egp"], price[meter], co2[meter])
            recs.append({"meter": meter, "solution": s["solution"], "saving_pct": float(s["saving_pct"]),
                         "capex_egp": float(s["capex_egp"]), "source": s["source"],
                         "annual_consumption": annual_qty, "unit": unit[meter],
                         "unit_price": price[meter], "unit_co2": co2[meter],
                         "waste_found_egp": float(ev["waste_egp"].sum()), **eco})
    return sorted(recs, key=lambda r: (r["payback_months"] is None, r["payback_months"] or 0))


def what_if(rec: dict, saving_pct: float = None, unit_price: float = None) -> dict:
    """Recompute a recommendation with a different saving % and/or unit price."""
    new = dict(rec)
    new["saving_pct"] = rec["saving_pct"] if saving_pct is None else saving_pct
    new["unit_price"] = rec["unit_price"] if unit_price is None else unit_price
    new.update(solution_economics(rec["annual_consumption"], new["saving_pct"], rec["capex_egp"],
                                  new["unit_price"], rec["unit_co2"]))
    return new


# ------------------------------------------------------------------- output
def _round(x, n=2):
    return None if x is None else round(float(x), n)


def _clean_rec(rec: dict) -> dict:
    return {k: (_round(v) if isinstance(v, (float, np.floating)) or v is None else v) for k, v in rec.items()}


def analyze(raw: pd.DataFrame, artifacts: dict, prices: dict = None, catalog_path=CATALOG_PATH) -> dict:
    """Full pipeline on new data. Returns a JSON-serializable dict (see API_CONTRACT.md)."""
    prices = {**REF, **(prices or {})}
    df = add_time_features(clean_data(raw))
    det = detect(df, artifacts)
    waste_res = add_residual_features(df, artifacts["clean_models"])  # healthy-trained residuals
    events = estimate_waste(waste_res, group_events(det), prices)
    recs = recommend(det, events, load_catalog(catalog_path), prices)

    total_egp = float(events["waste_egp"].sum())
    ev_list = []
    for i, ev in events.sort_values("start").reset_index(drop=True).iterrows():
        share = ev["waste_egp"] / total_egp if total_egp > 0 else 0
        ev_list.append({"id": i + 1, "start": ev["start"].isoformat(), "end": ev["end"].isoformat(),
                        "hours": int(ev["hours"]), "meter": ev["meter"], "meter_label": METER_LABELS[ev["meter"]],
                        "waste_qty": _round(ev["waste_qty"]), "unit": ev["unit"],
                        "waste_egp": _round(ev["waste_egp"]), "waste_co2_kg": _round(ev["waste_co2_kg"]),
                        "severity": "high" if share >= 0.20 else "medium" if share >= 0.05 else "low"})

    by_meter = (events.groupby("meter").agg(events=("start", "size"), waste_qty=("waste_qty", "sum"),
                                            waste_egp=("waste_egp", "sum"), waste_co2_kg=("waste_co2_kg", "sum"))
                .reset_index().sort_values("waste_egp", ascending=False))
    daily = (det.set_index(TIME_COL).resample("D")
             .agg(total_kwh=("total_kwh", "sum"), water_m3=("water_m3", "sum"),
                  fuel_liters=("fuel_liters", "sum"), flagged_hours=("is_flagged", "sum")).reset_index())

    short = len(df) < 24 * 30
    return {
        "meta": {"rows": len(df), "start": df[TIME_COL].min().isoformat(), "end": df[TIME_COL].max().isoformat(),
                 "flagged_hours": int(det["is_flagged"].sum()), "currency": "EGP", "prices": prices,
                 "warning": "Less than 30 days of data: annual figures are rough extrapolations." if short else None,
                 "disclaimer": DISCLAIMER},
        "summary": {"total_waste_egp": _round(total_egp), "total_waste_co2_kg": _round(events["waste_co2_kg"].sum()),
                    "num_events": len(events),
                    "by_meter": [{"meter": r.meter, "meter_label": METER_LABELS[r.meter], "events": int(r.events),
                                  "waste_qty": _round(r.waste_qty), "unit": unit_maps(prices)[2][r.meter],
                                  "waste_egp": _round(r.waste_egp), "waste_co2_kg": _round(r.waste_co2_kg)}
                                 for r in by_meter.itertuples()]},
        "events": ev_list,
        "recommendations": [_clean_rec(r) for r in recs],
        "daily": [{"date": r.timestamp.date().isoformat(), "total_kwh": _round(r.total_kwh),
                   "water_m3": _round(r.water_m3), "fuel_liters": _round(r.fuel_liters),
                   "flagged_hours": int(r.flagged_hours)} for r in daily.itertuples()],
    }


def analyze_records(records: list, artifacts: dict, prices: dict = None) -> dict:
    """Same as analyze() but takes a list of JSON records (one dict per hour)."""
    if not records:
        raise ValueError("No records supplied")
    return analyze(pd.DataFrame(records), artifacts, prices)
