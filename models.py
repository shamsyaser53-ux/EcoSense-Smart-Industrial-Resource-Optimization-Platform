from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    facility_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    records: Mapped[list["ConsumptionRecord"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan",
    )


class ConsumptionRecord(Base):
    __tablename__ = "consumption_records"

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "period_type",
            "period_date",
            name="uq_company_period_type_date",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), index=True
    )
    period_type: Mapped[str] = mapped_column(
        String(10), default="daily", index=True
    )
    period_date: Mapped[date] = mapped_column(Date, index=True)
    electricity_kwh: Mapped[float] = mapped_column(Float, default=0.0)
    water_m3: Mapped[float] = mapped_column(Float, default=0.0)
    fuel_liters: Mapped[float] = mapped_column(Float, default=0.0)
    data_source: Mapped[str] = mapped_column(String(20), default="measured")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )

    company: Mapped["Company"] = relationship(back_populates="records")


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    result: Mapped[dict] = mapped_column(JSON)


class SimulationResult(Base):
    __tablename__ = "simulation_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    scenarios_input: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict] = mapped_column(JSON)