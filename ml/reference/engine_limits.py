"""
Lycoming IO-540/O-540 series — published operating limits.

Sources (cite these exactly if asked):
- FAA Type Certificate Data Sheet No. 1E4, Revision 25 (Note 1, Note 2)
- Lycoming Operator's Manual, O-540/IO-540 Series, 4th Edition,
  FAA-approved, Section 3 (Operating Instructions)
- Lycoming.com, "Leaning Lycoming Engines" (official guidance page)

All values below are the engine manufacturer's/FAA's own published
numbers, not estimated or invented thresholds.
"""

# --- Temperature limits: absolute maximums (FAA TCDS, Note 1) ---
CHT_MAX_ABSOLUTE_F = 500          # cylinder head, well-type thermocouple
CYLINDER_BASE_MAX_F = 325         # n/a on internal-oil-jet-cooled variants
OIL_INLET_MAX_F = 245

# --- Temperature limits: recommended continuous, for max service life
#     (Operator's Manual Section 3) ---
CHT_CONTINUOUS_MIN_F = 150
CHT_CONTINUOUS_MAX_F = 435        # high-performance cruise ceiling
CHT_ECONOMY_CRUISE_MAX_F = 400    # economy cruise ceiling
OIL_TEMP_CONTINUOUS_MIN_F = 165
OIL_TEMP_CONTINUOUS_MAX_F = 220

# --- Pressure limits (FAA TCDS, Note 2) ---
OIL_PRESSURE_NORMAL_MIN_PSI = 55
OIL_PRESSURE_NORMAL_MAX_PSI = 95
OIL_PRESSURE_IDLE_MIN_PSI = 25
OIL_PRESSURE_STARTUP_MAX_PSI = 115
# Fuel pressure varies by exact engine variant (see TCDS Note 2 table) —
# set FUEL_PRESSURE_MIN_PSI / MAX_PSI once the specific UAV variant is
# confirmed; do not average across variants.
# TODO: confirm variant (currently referencing IO-540)
FUEL_PRESSURE_MIN_PSI = None
FUEL_PRESSURE_MAX_PSI = None

# --- Power management (Lycoming.com official guidance) ---
MAX_CONTINUOUS_LOAD_FRACTION = 0.65   # of rated HP, for max service life

# --- Overhaul interval ---
TBO_HOURS = 1800   # conservative end of published 1,800-2,000hr range

# --- Reference power table: IO-540-K/L/M/S series (300hp variant) ---
# Replace with the exact variant's table from TCDS if a different
# variant is confirmed for the target UAV.
# TODO: confirm variant (currently referencing IO-540)
RATED_HP = 300
RATED_RPM = 2700
PERFORMANCE_CRUISE_HP = 225   # 75% rated
ECONOMY_CRUISE_HP = 180       # 60% rated
