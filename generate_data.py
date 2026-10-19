"""EcoSense - synthetic factory data generator (one full year, one reading per hour).

- The data is synthetic, but the reference parameters (REF) are based on Egyptian/engineering figures.
- Deliberate anomalies are labeled in the columns is_anomaly and anomaly_type so the model can be
  evaluated against them (the model itself is trained without seeing these labels).
- Output: factory_data.csv. The solutions catalog is maintained by hand in solutions_catalog.csv.
"""
import numpy as np
import pandas as pd

rng = np.random.default_rng(42)

from ref_params import REF

idx = pd.date_range("2025-01-01", "2025-12-31 23:00", freq="h")
df = pd.DataFrame(index=idx)
n = len(df)
hour = idx.hour.values
dow = idx.dayofweek.values          # Monday=0 ... Friday=4 ... Saturday=5
doy = idx.dayofyear.values

# ---- Weather (roughly Cairo) ----
temp = (22 + 8 * np.sin(2 * np.pi * (doy - 110) / 365)
        + 5 * np.sin(2 * np.pi * (hour - 9) / 24) + rng.normal(0, 1.2, n))
df["temp_c"] = temp.round(1)

# ---- Production schedule: Saturday-Thursday, two shifts 06:00-22:00, Friday off ----
working = (dow != 4) & (hour >= 6) & (hour < 22)
prod = np.where(working, np.clip(rng.normal(0.85, 0.08, n), 0.5, 1.0), 0.0)
# Gradual ramp-up / ramp-down in the first and last hour
prod = np.where(working & ((hour == 6) | (hour == 21)), prod * 0.6, prod)
df["production_level"] = prod.round(3)

# ---- Sub-meters (kWh equals kW because readings are hourly) ----
machines = 18 + 220 * prod + rng.normal(0, 4, n)
air_cop = REF["chiller_cop_baseline"]
cool_thermal = (60 + 16 * np.maximum(temp - 16, 0)) * (0.4 + 0.6 * prod)
cooling = cool_thermal / air_cop + rng.normal(0, 2, n)
compressed = 38 + 85 * prod + rng.normal(0, 3, n)
lighting = np.where(working, 26, 4) + rng.normal(0, 0.8, n)
other = 20 + 10 * prod + rng.normal(0, 2, n)
water = 0.4 + 3.2 * prod + rng.normal(0, 0.1, n)        # m3/hour
fuel = 0.3 + 6.0 * prod + rng.normal(0, 0.3, n)         # liters/hour (generator / crane / boiler)

# ====== Anomaly injection ======
atype = np.array([""] * n, dtype=object)
def mark(mask, name):
    atype[mask] = np.where(atype[mask] == "", name, atype[mask])

def period(a, b):
    return (idx >= a) & (idx < b)

# 1) Compressed-air leak: constant extra load at night and during production (2 weeks)
m = period("2025-03-10", "2025-03-24")
compressed = compressed + np.where(m, 32 + rng.normal(0, 2, n), 0)
mark(m, "compressed_air_leak")

# 2) Chiller degradation (fouled heat exchanger) in summer: COP drops by 28%
m = period("2025-07-10", "2025-08-05")
cooling = np.where(m, cooling / 0.72, cooling)
mark(m, "chiller_degradation")

# 3) Lights left on at night: 14 random nights
nights = rng.choice(np.arange(0, 365), 14, replace=False)
m = np.isin(doy - 1, nights) & ((hour >= 22) | (hour < 6))
lighting = np.where(m, 26 + rng.normal(0, 0.8, n), lighting)
mark(m, "lights_left_on")

# 4) Machines running idle on Friday: 7 Fridays
fridays = np.where(dow == 4)[0]
chosen_days = rng.choice(np.unique(doy[fridays]), 7, replace=False)
m = np.isin(doy, chosen_days) & (dow == 4) & (hour >= 6) & (hour < 18)
machines = np.where(m, machines + 85, machines)
cooling = np.where(m, cooling + 8, cooling)
mark(m, "idle_machines_friday")

# 5) Water leak: one week (most visible at night)
m = period("2025-09-01", "2025-09-08")
water = water + np.where(m, 1.6, 0)
mark(m, "water_leak")

# 6) Short equipment spikes: 25 events, 1-3 hours each
starts = rng.choice(np.where(working)[0], 25, replace=False)
m = np.zeros(n, dtype=bool)
for s in starts:
    m[s:s + rng.integers(1, 4)] = True
machines = np.where(m, machines * 1.45, machines)
mark(m, "equipment_spike")

# ---- Assemble the table ----
df["machines_kwh"] = machines.round(2)
df["cooling_kwh"] = cooling.round(2)
df["compressed_air_kwh"] = compressed.round(2)
df["lighting_kwh"] = lighting.round(2)
df["other_kwh"] = other.round(2)
df["total_kwh"] = df[["machines_kwh", "cooling_kwh", "compressed_air_kwh",
                      "lighting_kwh", "other_kwh"]].sum(axis=1).round(2)
df["water_m3"] = np.clip(water, 0, None).round(3)
df["fuel_liters"] = np.clip(fuel, 0, None).round(2)
df["anomaly_type"] = atype
df["is_anomaly"] = (atype != "").astype(int)
df.index.name = "timestamp"
df.to_csv("factory_data.csv")

print(df.shape, "| anomalies:", df.is_anomaly.mean().round(3))
print(df.groupby("anomaly_type").size())
