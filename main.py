from contextlib import asynccontextmanager
from datetime import date, timedelta
import logging
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from config import settings
from database import get_db, init_db
from deps import get_current_user, get_optional_user
from models import Company, ConsumptionRecord, AnalysisResult
from auth_models import User
from routers import auth as auth_router
from routers import ml as ml_router
from routers import simulation as simulation_router
from routers import waste as waste_router
from services.cost_service import calculate_costs
from services.ml_service import run_analysis_records

logger = logging.getLogger("ecosense.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="EcoSense API",
    description=(
        "Unified EcoSense Industrial Resource Management & Anomaly Detection API. "
        "Provides multi-tenant SaaS features, company authentication, What-If simulation, "
        "and machine learning anomaly detection with ROI recommendations."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for frontend applications (configured via .env / config.py)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class UnifiedAnalyzeRequest(BaseModel):
    # ML Anomaly Detection fields (API_CONTRACT.md)
    records: list[dict] | None = Field(default=None, description="Hourly factory records for ML analysis")
    prices: dict | None = Field(default=None, description="Optional price overrides for ML analysis")

    # SaaS Aggregate Cost fields
    electricity_kwh: float | None = Field(default=None, ge=0)
    water_m3: float | None = Field(default=None, ge=0)
    fuel_liters: float | None = Field(default=None, ge=0)

    electricity_price_per_kwh: float | None = Field(default=None, ge=0)
    water_price_per_m3: float | None = Field(default=None, ge=0)
    fuel_price_per_liter: float | None = Field(default=None, ge=0)

    period_type: Literal["daily", "weekly", "monthly", "yearly"] = "daily"
    period_date: date | None = Field(default=None, description="Optional target date, defaults to today")


def get_period_start(period_type: str, target_date: date | None = None) -> date:
    ref_date = target_date or date.today()

    if period_type == "daily":
        return ref_date

    if period_type == "weekly":
        return ref_date - timedelta(days=ref_date.weekday())

    if period_type == "monthly":
        return ref_date.replace(day=1)

    if period_type == "yearly":
        return ref_date.replace(month=1, day=1)

    raise HTTPException(status_code=422, detail="Invalid period type")


@app.get("/")
def home():
    return {
        "message": "Welcome to EcoSense API",
        "status": "running",
        "version": "1.0.0",
        "docs": "/docs",
    }


@app.post("/analyze")
def analyze(
    data: UnifiedAnalyzeRequest,
    db: Session = Depends(get_db),
    optional_user: User | None = Depends(get_optional_user),
):
    """Unified analyze endpoint:
    - If 'records' is provided: runs ML anomaly detection & waste quantification.
    - If resource consumption numbers are provided: calculates costs for the authenticated company.
    """
    # 1. Path A: ML Hourly Records Analysis
    if data.records is not None:
        try:
            result = run_analysis_records(data.records, data.prices)
            if optional_user and optional_user.company_id:
                try:
                    row = AnalysisResult(
                        company_id=optional_user.company_id,
                        result={
                            "type": "ml_records",
                            "meta": result.get("meta"),
                            "summary": result.get("summary"),
                            "events_count": len(result.get("events", [])),
                        },
                    )
                    db.add(row)
                    db.commit()
                    result["analysis_saved"] = True
                    result["company_id"] = optional_user.company_id
                except Exception:
                    db.rollback()
                    logger.warning("Could not persist ML result for company %s", optional_user.company_id)
            return result
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
        except Exception:
            logger.exception("ML Analysis failed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal error while analyzing the data",
            )

    # 2. Path B: SaaS Aggregate Cost Analysis
    if data.electricity_kwh is None or data.water_m3 is None or data.fuel_liters is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Provide either 'records' for hourly ML anomaly detection or "
                "'electricity_kwh', 'water_m3', and 'fuel_liters' for aggregate cost analysis."
            ),
        )

    if not optional_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required for aggregate consumption tracking",
            headers={"WWW-Authenticate": "Bearer"},
        )

    company = (
        db.query(Company)
        .filter(Company.id == optional_user.company_id)
        .first()
    )
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")

    consumption = {
        "electricity_kwh": data.electricity_kwh,
        "water_m3": data.water_m3,
        "fuel_liters": data.fuel_liters,
    }

    unit_prices = {
        "electricity_kwh": data.electricity_price_per_kwh,
        "water_m3": data.water_price_per_m3,
        "fuel_liters": data.fuel_price_per_liter,
    }

    results = calculate_costs(consumption, unit_prices)
    period_start = get_period_start(data.period_type, data.period_date)

    record = (
        db.query(ConsumptionRecord)
        .filter(
            ConsumptionRecord.company_id == company.id,
            ConsumptionRecord.period_type == data.period_type,
            ConsumptionRecord.period_date == period_start,
        )
        .first()
    )

    if record is None:
        record = ConsumptionRecord(
            company_id=company.id,
            period_type=data.period_type,
            period_date=period_start,
            **consumption,
            data_source="measured",
        )
        db.add(record)
    else:
        record.electricity_kwh = data.electricity_kwh
        record.water_m3 = data.water_m3
        record.fuel_liters = data.fuel_liters

    analysis_row = AnalysisResult(
        company_id=company.id,
        result={
            **results,
            "period_type": data.period_type,
            "period_date": period_start.isoformat(),
        },
    )
    db.add(analysis_row)

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not save the analysis",
        ) from exc

    return {
        "company_name": company.name,
        "consumption_saved": True,
        "analysis_saved": True,
        "period_type": data.period_type,
        "period_date": period_start.isoformat(),
        **results,
        "notice": (
            "Enter the total consumption for the selected period. "
            "Costs use company-provided prices. Missing prices are not "
            "estimated. This endpoint does not detect waste or predict "
            "actual savings."
        ),
    }


# Include Routers
app.include_router(auth_router.router)
app.include_router(ml_router.router)
app.include_router(simulation_router.router)
app.include_router(waste_router.router)