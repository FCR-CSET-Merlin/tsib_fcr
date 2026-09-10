# Changelog

All notable changes to **tsib-fcr** (the Fraunhofer Chile Research fork of
[FZJ-IEK3-VSA/tsib](https://github.com/FZJ-IEK3-VSA/tsib)) are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Versions `0.2.x+cl` were internal pre-releases of the fork and were never tagged.
`1.0.0` is the first stable, tagged release.

---

## [1.0.0] — 2026-09-10

First stable release of the Chile fork. It packages, as a single supported API,
all Chile-specific adaptations that were developed incrementally over the
`0.2.x+cl` pre-releases, plus the high-priority requests from the MERLIN_RCP
integrator (hourly setpoints, HVAC availability masks, DHW, `t_mains`).

From here on the public surface described in [`README.md`](README.md) and the
MERLIN_RCP interface contract in [`AGENT.md`](AGENT.md) are covered by SemVer:
breaking changes require a `2.0.0`.

### Relative to upstream FZJ tsib 0.2.x

#### Added — Chilean building stock

- **`country="CL"`** accepted by `BuildingConfiguration`, with `KWARG_DEFAULTS_CL`:
  heating setpoint 18 °C, cooling setpoint 26 °C, infiltration 0.8 ACH,
  heating system `"Electric heater"`.
- **`CL_episcope.csv` — 810 fully resolved Chilean archetypes**: 3 building types
  (`SFH`, `MFH`, `AB`) × 5 vintage periods (`preRT`, `RT1`, `RT2`, `CEV`,
  `post2021`) × 6 materials (`mad`, `lad`, `hor`, `met`, `prefab`, `adobe`) ×
  9 thermal zones (`A`–`I`, Chile's `zona_termica`). Every row carries its
  geometry **and** its zone/period/material-specific U-values — no runtime
  U-value lookup or injection needed.
- **5-segment archetype IDs** `CL.{BuildingType}.{Period}.{Material}.{Zone}`
  (e.g. `CL.SFH.RT2.hor.D`), usable directly as `ID`.
- **`material` and `thermalZone` kwargs** for archetype resolution without an
  explicit `ID` (resolved together with `buildingYear` / `buildingType`).
- **U-value data pipeline** (build-time only, not imported at runtime):
  - `build_cl_zone_uvalues.py` aggregates ~229k real CEV (Calificación
    Energética de Viviendas) records into the diagnostic `CL_zone_uvalues.csv`
    (270 rows), with a documented pooled-median fallback hierarchy for
    under-sampled cells.
  - `met` and `adobe` wall U-values come from MINVU DITEC "Listado Oficial de
    Soluciones Constructivas" (0.75 W/m²K) and NCh853 Annex A (1.38 W/m²K)
    respectively, because CEV has no reliable data for them.
  - `build_cl_episcope.py` merges the U-value table with the 27-row
    hand-authored geometry seed `CL_episcope_base.csv` into `CL_episcope.csv`.
- **`Code_BuildingSizeClass`** column in `CL_episcope.csv` (required for
  building-type filtering; absence caused fallback to European archetypes).
- **U-value override kwargs** registered in `KWARG_TYPES` and applied at the end
  of `_get_fabric` so they always win over the archetype row: `U_Wall_1`,
  `U_Roof_1`, `U_Floor_1`, `U_Window_1`, `n_Infiltration`, `g_gl_n`.
- **Regional residential-electricity calibration (Chile, 2024)**: new `region`
  kwarg (integer 1–16) normalizes the default hourly `elecLoad` from
  `kwh_por_persona_p11a` (BNE 2024 regional balance ÷ Census 2024 residents on
  the public grid), in `tsib/data/chile/consumo_electrico_residencial_regional_2024.csv`.
  Exposes `electricityKwhPerPersonYear`, `electricityKwhPerApartmentYear`,
  `electricityProfileSource` on the cfg. `autoProfileElectricityKwhPerApartment`
  overrides it; with neither, the backwards-compatible 2500 kWh/apartment/year
  default is kept. Hourly shape unchanged — only annual normalization.
- **Chilean monthly thermal-zone setpoints**: `tsib/setpoints.py` +
  `tsib/data/chile/thermal_setpoints_by_zone_month.csv`
  (9 zones × 12 months heating/cooling setpoints).
- **Deterministic default occupancy profiles**: reproducible
  occupancy / internal-gain defaults in `tsib/profiles.py` and `buildingmodel.py`,
  replacing the removed stochastic generator (see *Removed*).
- **Geo data**: Providencia validated building database
  (`test/buildings_providencia_validated.gpkg`) and a comuna → thermal-zone
  crosswalk (`tsib/data/geo/comuna_zona_termica.json`,
  `tsib/data/geo/build_comuna_zona_termica.py`).

#### Added — weather adapter

- **`tsib.bd_tmy_to_tsib(df)`** — adapter from BD Ancestral TMY to tsib's
  weather format (`T`, `DHI`, `DNI`, `GHI`, …), in `tsib/weather/chile.py`.
- **Water-mains temperature (`t_mains`) handling** in `bd_tmy_to_tsib`:
  recognizes 13 input column aliases (`t_mains`, `t_red`, `temperatura_red`, …);
  `t_mains_nan_policy` = `"raise"` / `"interpolate"` / `"fallback_from_tdry"`;
  when no column is present it emits a `UserWarning` and estimates `t_mains`
  from a 30-day rolling mean of dry-bulb temperature, recording the provenance
  in `attrs["t_mains_source"]`. `require_t_mains=True` raises instead. Old TMYs
  without a mains column keep working unchanged.

#### Added — solver-free demand path

- **`Building5R1C.sim_demand_direct()`** — computes annual heating and cooling
  demand by solving the ISO 13790 5R1C balance analytically per hour, with **no
  LP and no solver**. Forward-Euler time loop with up to 5 iterations for the
  annual periodic boundary condition (< 0.01 K convergence). Writes hourly
  `Heating Load`, `Cooling Load`, `Electricity Load`, `T_air`, `T_s`, `T_m`,
  `Heating Setpoint`, `Cooling Setpoint` to `model.detailedResults`.
- **Hourly setpoints**: `heating_setpoint` / `cooling_setpoint` accept
  scalar / list / `np.ndarray` / `pd.Series`; normalized to an hourly array
  aligned to the weather index; validated as finite and strictly ordered
  (`cooling > heating` every hour), `ValueError` otherwise. `None` reproduces
  the historical constant-setpoint behavior exactly.
- **HVAC availability masks**: `heating_available` / `cooling_available`
  boolean hourly masks represent "system switched off" by leaving the indoor
  air in free-float (load = 0) — **without** infinite or extreme finite
  setpoints.
- **`sim_demand()`** kept as a no-argument alias of `sim_demand_direct()`.
- **`Q_ig` normalization**: internal-gain input accepts scalar / list /
  `np.ndarray` / `pd.Series` via `as_hourly_series`, rejecting non-finite
  values and length mismatches.

#### Added — profile & DHW utilities (`tsib/profiles.py`, exported at package level)

- **`calculate_dhw_load(...)`** — domestic-hot-water *useful thermal* demand
  from a water-mains temperature series, independent of any DHW equipment.
  Returns `DHW Load` [kWh/h], `DHW Liters`, `DHW DeltaT`, `T_mains`;
  `t_mains_nan_policy` = `"raise"` / `"interpolate"`.
- **`as_hourly_series(value, index, name)`** — scalar/array/Series → validated
  hourly array.
- **`normalize_daily_shape(...)`** — tile weekday/weekend 24-value shapes over
  a year (with optional holidays).
- **`normalize_profile_to_annual_energy(profile, annual_kwh)`** — scale a
  relative profile to a target annual sum.
- **`convert_thermal_to_final(load, efficiency=None, cop=None)`** — useful
  thermal → final energy helper, deliberately kept out of the thermal engine.

#### Added — tests, examples, docs

- **`test/test_chile.py`** — 33 tests covering `country="CL"` acceptance,
  archetype resolution, `sim_demand_direct` setpoint/availability semantics and
  backwards compatibility, `Q_ig` input forms, `bd_tmy_to_tsib` `t_mains`
  handling, and `calculate_dhw_load`.
- **Examples**:
  `examples/chile/validation_direct_5r1c.py`,
  `examples/chile/validation_dhw.py`,
  `examples/chile/simulate_dwelling_database.py`,
  `examples/santiago_AB/santiago_ab_calibration.py` (219-unit concrete
  apartment block in downtown Santiago calibrated against monthly gas billing).
- Rewritten `README.md` (current public API) and `AGENT.md` (engineering guide
  + MERLIN_RCP interface contract). The original adaptation proposal is kept as
  `legacy_tsib_fcr_CLAUDE.md` for historical context only.
- `feature-request/electric_demand/README.md` documents the regional
  electricity source, denominators and methodological scope.

### Changed

- **Package renamed** `tsib` → `tsib-fcr`; author, description, URL and
  keywords updated for the fork. `Development Status` classifier raised from
  *4 - Beta* to *5 - Production/Stable*; `python_requires=">=3.9"`; obsolete
  Python 2.x / 3.4–3.6 classifiers dropped.
- **HiGHS is the default solver** for the optimization path (`sim5R1C`);
  install with `pip install highspy`. The demand path needs no solver.
- **HVAC-off guidance** switched from extreme setpoints to availability masks
  throughout docs and examples.
- Archetype lookup can consume a direct archetype `ID` during the CSV lookup.
- `tinydb` import made optional (no `ImportError` when it is not installed).
- `numpy` deprecation fix (`np.bool`).

### Removed

- **`getHouseholdProfiles()` and the `tsorb` dependency** — upstream's
  stochastic occupancy / electricity / DHW generator. `tsorb` calls
  `pd.datetime(...)`, removed in pandas ≥ 1.0, and is unfixable under this
  project's pinned pandas 2.2.3 without patching the installed package.
  `Building._get_occupancy_profile()` still references it, so that code path is
  **dead** and raises `AttributeError` if reached. Inject `Q_ig`, `elecLoad`,
  `occ_nothome`, `occ_sleeping`, `hotWaterLoad` into the cfg yourself instead
  (see README). Reactivation notes are in the README.
- **`VisualizeOccupancy`** script and related household-profile helpers.
- **`tsam`** dependency (time-series aggregation), unused by this fork.

### Known limitations

- No stochastic occupancy model (see *Removed*); callers supply their own
  deterministic or modelled profiles.
- `n_Infiltration` and `g_gl_n` are not zone-specific (CEV has no data) — they
  use the zone-neutral per-material/period values from `CL_episcope_base.csv`,
  overridable manually.
- `post2021` archetypes rest on a small CEV sample — treat with caution.
- The regional electricity baseline is *total observed* residential
  electricity and may already include electric space heating / cooling / DHW;
  it must be reconciled against — not added to — the simulated end uses.

---

## [0.2.2+cl] — pre-release (untagged)

- Regional residential-electricity calibration (BNE 2024 / Census 2024).
- Removed obsolete `feature-request/` documents.
- Author information and fork description updated in `setup.py`; `.claude`
  added to `.gitignore`.

## [0.2.1+cl] — pre-release (untagged)

- `CL_episcope.csv` expanded to 810 fully resolved rows: zone/period/material
  U-values baked in, 6 materials (incl. `met`/`adobe` literature constants),
  5-segment IDs. Retired the separate runtime zone-U-value table and
  period-binning function.
- Providencia building database and comuna → thermal-zone crosswalk.
- Deterministic default occupancy profiles; monthly thermal-zone setpoint
  table and `tsib/setpoints.py`.
- Hourly setpoints, HVAC availability masks, `calculate_dhw_load`, and
  `t_mains` support added to the direct 5R1C path (MERLIN_RCP feature request).
- Direct archetype `ID` consumed during lookup; `Code_BuildingSizeClass`
  column added; `tinydb` made optional.

## [0.2.0+cl] — pre-release (untagged)

- Initial Chile adaptation: `country="CL"`, `KWARG_DEFAULTS_CL`, U-value
  override block, first `CL_episcope.csv` (27-row seed), `tsib/weather/chile.py`
  with `bd_tmy_to_tsib`, `test/test_chile.py`.
- `tsorb` dependency and `getHouseholdProfiles()` removed (pandas ≥ 2.0
  incompatibility).
- PEP 440-compliant local version label; package renamed to `tsib-fcr`.

---

## Upstream base

This fork diverged from FZJ-IEK3-VSA/tsib around its `0.2.x` line (HiGHS
default solver, Python 3.9, reworked typical-building querying). For upstream
history before the fork, see the
[upstream repository](https://github.com/FZJ-IEK3-VSA/tsib).

[1.0.0]: https://github.com/FCR-CSET-Merlin/tsib_fcr/releases/tag/v1.0.0
