from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./ecosense.db"
    cors_origins: str = "http://localhost:3000,http://localhost:5173,http://127.0.0.1:5500"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()

# ---------------------------------------------------------------------------
# DEMO ASSUMPTIONS - placeholders for the prototype, NOT real market data.
# Replace with real tariffs / regional factors before any real-world use.
# ---------------------------------------------------------------------------
DEMO_PRICES = {
    "electricity": {"unit": "kWh", "price_per_unit": 0.15},   # USD per kWh
    "water": {"unit": "m3", "price_per_unit": 2.50},          # USD per cubic meter
    "fuel": {"unit": "liter", "price_per_unit": 1.20},        # USD per liter
}

# Assumed share of each resource's cost that could be saved (ESTIMATES)
DEMO_SAVINGS_RATES = {
    "electricity": 0.15,
    "water": 0.10,
    "fuel": 0.12,
}

# DEMO emission factors (kg CO2e per unit). Real values vary by country/grid/fuel.
EMISSION_FACTORS = {
    "electricity": {"factor": 0.40, "unit": "kg CO2e per kWh"},
    "water": {"factor": 0.30, "unit": "kg CO2e per m3"},
    "fuel": {"factor": 2.68, "unit": "kg CO2e per liter (diesel)"},
}

DISCLAIMER = (
    "All prices, savings rates, and emission factors are DEMO assumptions. "
    "Estimated savings are rough estimates, not guarantees."
)