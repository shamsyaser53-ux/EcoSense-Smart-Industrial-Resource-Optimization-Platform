from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, Field, model_validator


NonNegFloat = Annotated[
    float,
    Field(ge=0, allow_inf_nan=False),
]


class WasteDetectionRequest(BaseModel):
    period_date: date | None = Field(
        None,
        description="Period being analyzed. Defaults to today.",
    )
    period_type: Literal[
        "daily", "weekly", "monthly", "yearly"
    ] = "daily"

    electricity_kwh: NonNegFloat | None = None
    water_m3: NonNegFloat | None = None
    fuel_liters: NonNegFloat | None = None

    electricity_price_per_kwh: NonNegFloat | None = None
    water_price_per_m3: NonNegFloat | None = None
    fuel_price_per_liter: NonNegFloat | None = None

    lookback_periods: int = Field(6, ge=1, le=24)
    min_history_periods: int = Field(3, ge=2, le=24)

    warning_threshold_percent: float = Field(
        10.0, gt=0, le=1000, allow_inf_nan=False
    )
    high_threshold_percent: float = Field(
        25.0, gt=0, le=1000, allow_inf_nan=False
    )

    save_result: bool = True

    @model_validator(mode="after")
    def check(self):
        if all(
            value is None
            for value in (
                self.electricity_kwh,
                self.water_m3,
                self.fuel_liters,
            )
        ):
            raise ValueError(
                "Provide at least one resource consumption value."
            )

        if (
            self.high_threshold_percent
            <= self.warning_threshold_percent
        ):
            raise ValueError(
                "High threshold must be greater than warning threshold."
            )

        if self.min_history_periods > self.lookback_periods:
            raise ValueError(
                "min_history_periods cannot exceed lookback_periods."
            )

        return self