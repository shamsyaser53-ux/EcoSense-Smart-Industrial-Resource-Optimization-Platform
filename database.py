from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import settings


connect_args = (
    {"check_same_thread": False}
    if settings.database_url.startswith("sqlite")
    else {}
)

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency: gives each request its own database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _migrate_sqlite_consumption_records():
    """Add period types while preserving existing consumption records."""

    if not settings.database_url.startswith("sqlite"):
        return

    inspector = inspect(engine)

    if "consumption_records" not in inspector.get_table_names():
        return

    columns = {
        column["name"]
        for column in inspector.get_columns("consumption_records")
    }

    if "period_type" in columns:
        return

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE consumption_records_new (
                    id INTEGER NOT NULL PRIMARY KEY,
                    company_id INTEGER NOT NULL,
                    period_type VARCHAR(10) NOT NULL DEFAULT 'daily',
                    period_date DATE NOT NULL,
                    electricity_kwh FLOAT NOT NULL DEFAULT 0.0,
                    water_m3 FLOAT NOT NULL DEFAULT 0.0,
                    fuel_liters FLOAT NOT NULL DEFAULT 0.0,
                    data_source VARCHAR(20) NOT NULL DEFAULT 'measured',
                    created_at DATETIME NOT NULL,
                    CONSTRAINT uq_company_period_type_date
                    UNIQUE (company_id, period_type, period_date),
                    FOREIGN KEY(company_id) REFERENCES companies(id)
                )
                """
            )
        )

        connection.execute(
            text(
                """
                INSERT INTO consumption_records_new (
                    id,
                    company_id,
                    period_type,
                    period_date,
                    electricity_kwh,
                    water_m3,
                    fuel_liters,
                    data_source,
                    created_at
                )
                SELECT
                    id,
                    company_id,
                    'daily',
                    period_date,
                    electricity_kwh,
                    water_m3,
                    fuel_liters,
                    data_source,
                    created_at
                FROM consumption_records
                """
            )
        )

        connection.execute(
            text("DROP TABLE consumption_records")
        )

        connection.execute(
            text(
                """
                ALTER TABLE consumption_records_new
                RENAME TO consumption_records
                """
            )
        )


def init_db():
    import models  # noqa: F401
    import auth_models  # noqa: F401

    _migrate_sqlite_consumption_records()

    Base.metadata.create_all(bind=engine)