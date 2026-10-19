"""Reference constants used for EGP and CO2 conversion. Last reviewed: 2026-10-11.

Every value has a source below. Items marked VERIFY must be re-checked before the final demo.
"""
REF = {
    "tariff_egp_per_kwh": 2.55,  # EgyptERA, industrial medium voltage (11-22 kV), April 2026; Aug 2026 rise was household only
    "grid_emission_kg_per_kwh": 0.44,  # Egypt grid ~0.44 kgCO2e/kWh (Ember-based, 2024-25); sources range 0.44-0.56
    "diesel_egp_per_liter": 20.5,  # Ministry of Petroleum, since 10 Mar 2026, still valid on 9 Oct 2026; pricing committee meets in Oct - VERIFY
    "diesel_emission_kg_per_liter": 2.69,  # US EPA GHG Emission Factors Hub: 10.18 kg CO2/gal stationary diesel
    "water_egp_per_m3": 4.55,  # Last industrial tariff found (HCWW, 2018). Likely higher now, excludes sewage fee - use your bill
    "chiller_cop_baseline": 3.2,  # Typical air-cooled chiller 2.5-3.5; only used by the data generator
}

# Industrial tariff by connection voltage (EgyptERA, EGP/kWh, from April 2026)
TARIFF_BY_VOLTAGE_EGP = {
    "extra_high_220_132kV": 1.89,
    "high_66_33kV": 2.05,
    "medium_22_11kV": 2.55,
    "low_380V": 2.74,
}

SOURCES = {
    "tariff_egp_per_kwh": "https://egyptera.org/en/TarrifApril2026.aspx (assumes power factor 0.92). Press (Aug 2026): increase applied to household tiers only. NEW from 1 Oct 2026: grid-usage charge on medium voltage rises from 19.09 to 34.41 piastres/kWh (vetogate.com/5739999) - may add ~0.15 EGP/kWh for some customers",
    "grid_emission_kg_per_kwh": "Ember / lowcarbonpower.org (2024: 447, 2025: ~440 gCO2e/kWh); The Climate Registry 2024 default factors (Egypt 450-457 g in 2010-11); IEA Emissions Factors 2024",
    "diesel_egp_per_liter": "Ministry of Petroleum via sis.gov.eg/en/media-center/news/petroleum-ministry-new-fuel-prices-take-effect-in-egypt/",
    "diesel_emission_kg_per_liter": "https://www.epa.gov/system/files/documents/2022-04/ghg_emission_factors_hub.pdf (10.18 kg/gal / 3.785 L)",
    "water_egp_per_m3": "Cabinet decision 1730/2017 (industrial 3.35 EGP/m3) and Mada Masr June 2018 (4.55). A July 2026 press report says tariffs for economic activities were raised but gives no figure. Sewage fee (~63-65% of water bill for households) and 14% VAT are NOT included.",
}
