"""EcoSense Standalone ML Service. Run with: uvicorn app:app --reload"""
import io
import json
import logging
from pathlib import Path

import pandas as pd
from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from services.ml_service import (
    get_artifacts,
    get_defaults,
    run_analysis,
    run_analysis_records,
    run_demo,
    run_what_if,
    validate_prices,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("ecosense.api")

MAX_CSV_BYTES = 15 * 1024 * 1024  # 15 MB

app = FastAPI(
    title="EcoSense ML API",
    description="Standalone Machine Learning anomaly detection and waste estimation API.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    records: list[dict]  # one dict per hour, see API_CONTRACT.md
    prices: dict | None = None  # optional overrides of REF keys


class WhatIfRequest(BaseModel):
    recommendation: dict  # one item from /analyze -> recommendations
    saving_pct: float | None = Field(default=None, ge=0, le=1)
    unit_price: float | None = Field(default=None, gt=0)


def _check_prices(prices, currency=None):
    try:
        return validate_prices(prices, currency=currency)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


def _parse_prices(text, currency=None):
    if not text:
        return None
    try:
        prices = json.loads(text)
    except json.JSONDecodeError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "prices must be valid JSON, e.g. {\"tariff_egp_per_kwh\": 2.5}",
        )
    if not isinstance(prices, dict):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "prices must be a JSON object")
    return _check_prices(prices, currency=currency)


@app.get("/health")
def health():
    try:
        artifacts = get_artifacts()
        return {"status": "ok", "trained_rows": artifacts["trained_rows"]}
    except Exception as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc))


@app.post("/analyze")
def analyze_json(req: AnalyzeRequest):
    try:
        return run_analysis_records(req.records, req.prices)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    except Exception:
        logger.exception("Analysis failed")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal error while analyzing the data")


@app.get("/defaults")
def defaults():
    """Default prices for the input boxes, plus the tariff by voltage level."""
    return get_defaults()


@app.post("/analyze-csv")
def analyze_csv(
    file: UploadFile = File(...),
    prices: str | None = Form(default=None),
    facility: str | None = Form(default=None),
    currency: str | None = Form(default=None),
):
    contents = file.file.read(MAX_CSV_BYTES + 1)
    if len(contents) > MAX_CSV_BYTES:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"File exceeds maximum allowed size of {MAX_CSV_BYTES // (1024 * 1024)}MB",
        )
    try:
        raw = pd.read_csv(io.BytesIO(contents))
    except Exception:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Could not read the file as CSV")

    validated_prices = _parse_prices(prices, currency=currency)
    try:
        result = run_analysis(raw, validated_prices)
        if facility and "meta" in result:
            result["meta"]["facility"] = facility
        if currency and "meta" in result:
            result["meta"]["currency"] = currency
        return result
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    except Exception:
        logger.exception("Analysis failed")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal error while analyzing the data")


@app.get("/demo")
def demo(
    tariff_egp_per_kwh: float | None = None,
    water_egp_per_m3: float | None = None,
    diesel_egp_per_liter: float | None = None,
):
    """Analyze the bundled demo year. Optional query parameters override the default prices."""
    prices = {
        k: v
        for k, v in [
            ("tariff_egp_per_kwh", tariff_egp_per_kwh),
            ("water_egp_per_m3", water_egp_per_m3),
            ("diesel_egp_per_liter", diesel_egp_per_liter),
        ]
        if v is not None
    }
    try:
        return run_demo(_check_prices(prices))
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    except Exception:
        logger.exception("Demo failed")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal error while running demo")


@app.post("/what-if")
def what_if_endpoint(req: WhatIfRequest):
    try:
        return run_what_if(req.recommendation, req.saving_pct, req.unit_price)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    except Exception:
        logger.exception("What-If failed")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "What-If calculation failed")
