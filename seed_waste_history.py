from datetime import date, timedelta

from database import SessionLocal, init_db
from auth_models import User
from models import ConsumptionRecord

EMAIL = "ecosense.test@example.com"


def main():
    init_db()
    db = SessionLocal()

    try:
        user = db.query(User).filter(User.email == EMAIL).first()

        if user is None:
            print("Test user not found. Check the email.")
            return

        company_id = user.company_id

        demo_data = [
            (date.today() - timedelta(days=3), 1000, 100, 200),
            (date.today() - timedelta(days=2), 1000, 100, 200),
            (date.today() - timedelta(days=1), 1000, 100, 200),
        ]

        added = 0

        for period_date, electricity, water, fuel in demo_data:
            existing = (
                db.query(ConsumptionRecord)
                .filter(
                    ConsumptionRecord.company_id == company_id,
                    ConsumptionRecord.period_date == period_date,
                )
                .first()
            )

            if existing:
                print(f"Skipping existing record for {period_date}")
                continue

            db.add(
                ConsumptionRecord(
                    company_id=company_id,
                    period_date=period_date,
                    electricity_kwh=electricity,
                    water_m3=water,
                    fuel_liters=fuel,
                    data_source="demo",
                )
            )
            added += 1

        db.commit()
        print(f"Demo history added successfully. Added: {added}")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()