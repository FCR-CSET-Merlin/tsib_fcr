# -*- coding: utf-8 -*-
"""Phase 5 validation of the 5R1C wood-stove model with GeoNode data.

The script reads one Chilean dwelling from ``merlin_rcp.edificios``, obtains
its communal CUT and loads a complete local calendar year from
``meteorology_commune.era5_hourly_comunal``. It then runs the direct 5R1C
model and evaluates low/mid/high useful-heating coverage scenarios with the
wood-stove system-layer model.

Credentials are read from the standard ``GEONODE_*`` environment variables.
An optional env file can be supplied for local development; it is never
written to the repository.

Example from the repository root::

    PYTHONPATH=. python examples/chile/validate_wood_stove_geonode.py \
        --env-file /home/pca/merlin/geonode_connection/.env \
        --edificio-id 1690556 \
        --year 2024 \
        --output /tmp/wood_stove_validation.csv

The default dwelling is a deterministic representative candidate from
Concepcion: a single-family dwelling, classified as a wood-heating user, with
the median area/person count among a filtered regional cohort at the time the
case was selected. Change ``--edificio-id`` for another database snapshot.

This script separates useful-heating coverage sensitivities from the built-in
REDPE 2020 regional range. The REDPE scenarios are reference fuel targets,
not a claim that one dwelling has been individually calibrated.
"""

from __future__ import annotations

import argparse
import os
import shlex
from pathlib import Path

import numpy as np
import pandas as pd
import tsib
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL


DEFAULT_BUILDING_ID = 1690556
DEFAULT_YEAR = 2024
DEFAULT_EFFICIENCY = 0.50
SCENARIO_USEFUL_COVERAGE = {
    "low": 0.50,
    "mid": 0.75,
    "high": 1.00,
}
PERIOD_TO_REPRESENTATIVE_YEAR = {
    "preRT": 1990,
    "RT1": 2003,
    "RT2": 2011,
    "CEV": 2018,
    "post2021": 2022,
}


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--edificio-id", type=int, default=DEFAULT_BUILDING_ID)
    parser.add_argument("--year", type=int, default=DEFAULT_YEAR)
    parser.add_argument("--efficiency", type=float, default=DEFAULT_EFFICIENCY)
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Optional local file with GEONODE_* assignments; never committed.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional CSV path for scenario results.",
    )
    return parser.parse_args()


def _load_env_file(path: Path | None):
    """Load simple KEY=VALUE assignments without adding python-dotenv."""
    if path is None:
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        parsed = shlex.split(value.strip())
        if key and parsed and key not in os.environ:
            os.environ[key] = parsed[0]


def _required_env(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"Missing {name}. Set the GEONODE_* variables or pass --env-file."
        )
    return value


def _create_engine():
    return create_engine(
        URL.create(
            drivername="postgresql+psycopg2",
            host=_required_env("GEONODE_HOST"),
            port=int(_required_env("GEONODE_PORT")),
            username=_required_env("GEONODE_USER"),
            password=_required_env("GEONODE_PASSWORD"),
            database=_required_env("GEONODE_DATABASE"),
        ),
        pool_pre_ping=True,
        connect_args={"connect_timeout": 10},
    )


def _load_building(engine, edificio_id):
    query = text(
        """
        SELECT
            e.edificio_id,
            e.codigo_comuna,
            COALESCE(c.cut_comuna, e.codigo_comuna) AS tmy_commune_id,
            c.cut_region AS codigo_region,
            c.nombre_comuna,
            e.longitud,
            e.latitud,
            e.n_inmuebles,
            e.area_total_construida,
            e.area_promedio_inmueble,
            e.clasificacion,
            e.episcope_archetype,
            e.zona_termica,
            e.anio_construccion,
            e.n_pers_edificio,
            e.tipo_comb_calef
        FROM merlin_rcp.edificios AS e
        LEFT JOIN merlin_rcp.comunas_sii_cut AS c
          ON c.codigo_sii = e.codigo_comuna
        WHERE e.edificio_id = :edificio_id
        """
    )
    with engine.connect() as connection:
        row = connection.execute(query, {"edificio_id": int(edificio_id)}).mappings().fetchone()
    if row is None:
        raise ValueError(f"No building found for edificio_id={edificio_id}.")
    return dict(row)


def _load_era5_weather(engine, commune_id, year):
    """Load a complete local calendar year while querying in UTC."""
    start_local = pd.Timestamp(f"{year}-01-01", tz="America/Santiago")
    end_local = pd.Timestamp(f"{year + 1}-01-01", tz="America/Santiago")
    start_utc = start_local.tz_convert("UTC")
    end_utc = end_local.tz_convert("UTC")

    query = text(
        """
        SELECT timestamp_utc, ghi, dni, dhi, tdry, t_mains
        FROM meteorology_commune.era5_hourly_comunal
        WHERE commune_id = :commune_id
          AND timestamp_utc >= :start_utc
          AND timestamp_utc < :end_utc
        ORDER BY timestamp_utc
        """
    )
    with engine.connect() as connection:
        weather = pd.read_sql_query(
            query,
            connection,
            params={
                "commune_id": int(commune_id),
                "start_utc": start_utc,
                "end_utc": end_utc,
            },
        )

    if weather.empty:
        raise ValueError(
            f"No ERA5 weather found for commune_id={commune_id}, year={year}."
        )

    index_utc = pd.DatetimeIndex(pd.to_datetime(weather.pop("timestamp_utc"), utc=True))
    expected_utc = pd.date_range(
        start_utc, end_utc, freq="h", inclusive="left", tz="UTC"
    )
    if not index_utc.equals(expected_utc):
        raise ValueError(
            "ERA5 coverage must be a complete, ordered, duplicate-free local "
            f"calendar year: expected {len(expected_utc)} rows, got {len(index_utc)}."
        )

    required = ["ghi", "dni", "dhi", "tdry", "t_mains"]
    missing = [column for column in required if column not in weather]
    if missing:
        raise ValueError(f"ERA5 view is missing required columns: {missing}")
    numeric = weather[required].apply(pd.to_numeric, errors="coerce")
    if not np.isfinite(numeric.to_numpy(dtype=float)).all():
        raise ValueError("ERA5 view contains null or non-finite required values.")
    if (numeric[["ghi", "dni", "dhi"]] < 0).any().any():
        raise ValueError("ERA5 view contains negative irradiance values.")

    weather.index = index_utc.tz_convert("America/Santiago")
    weather.index.name = "timestamp_local"
    weather = weather.rename(columns={"tdry": "tdry"})
    return tsib.bd_tmy_to_tsib(weather, require_t_mains=True)


def _archetype_parameters(code):
    parts = str(code or "").split(".")
    if len(parts) != 5 or parts[0] != "CL":
        raise ValueError(
            f"Invalid Chilean episcope_archetype={code!r}; expected "
            "CL.{type}.{period}.{material}.{zone}."
        )
    _, building_type, period, material, thermal_zone = parts
    if period not in PERIOD_TO_REPRESENTATIVE_YEAR:
        raise ValueError(f"Unsupported archetype period: {period!r}")
    if building_type not in {"SFH", "MFH", "AB"}:
        raise ValueError(f"Unsupported archetype building type: {building_type!r}")
    if thermal_zone not in set("ABCDEFGHI"):
        raise ValueError(f"Unsupported Chilean thermal zone: {thermal_zone!r}")
    return {
        "building_type": building_type,
        "period": period,
        "material": material,
        "thermal_zone": thermal_zone,
        "building_year": PERIOD_TO_REPRESENTATIVE_YEAR[period],
    }


def _build_model(building, weather, winter_heating_setpoint=None):
    """Build and solve 5R1C, optionally overriding June-August heating setpoints."""
    archetype = _archetype_parameters(building["episcope_archetype"])
    n_units = int(building["n_inmuebles"] or 1)
    n_units = max(n_units, 1)
    area_m2 = float(building["area_promedio_inmueble"] or 60.0)
    raw_persons = building["n_pers_edificio"]
    persons = int(round(float(raw_persons) / n_units)) if raw_persons else 3
    persons = max(1, min(persons, 8))

    cfg_args = {
        "country": "CL",
        "buildingYear": archetype["building_year"],
        "buildingType": archetype["building_type"],
        "material": archetype["material"],
        "thermalZone": archetype["thermal_zone"],
        "setpointProfile": "chile_monthly",
        "a_ref": area_m2,
        "weatherData": weather,
        "weatherID": f"era5_commune_{building['tmy_commune_id']}",
        "n_persons": persons,
        "refurbishment": False,
        "autoProfiles": False,
        "longitude": float(building["longitud"]),
        "latitude": float(building["latitud"]),
    }
    cfg = tsib.BuildingConfiguration(cfg_args, ignore_profiles=True).getBdgCfg(
        includeSupply=True
    )
    zeros = pd.Series(np.zeros(len(weather)), index=weather.index)
    cfg.update(
        {
            "Q_ig": np.full(len(weather), persons * 0.08 + area_m2 * 0.004),
            "occ_nothome": zeros,
            "occ_sleeping": zeros,
            "elecLoad": zeros,
            "hotWaterLoad": zeros,
        }
    )

    model = tsib.Building5R1C(cfg)
    if winter_heating_setpoint is None:
        model.sim_demand_direct()
    else:
        heating_setpoint = pd.Series(
            cfg["heatingSetpointProfile"], index=weather.index
        )
        cooling_setpoint = pd.Series(
            cfg["coolingSetpointProfile"], index=weather.index
        )
        winter = heating_setpoint.index.month.isin((6, 7, 8))
        heating_setpoint.loc[winter] = float(winter_heating_setpoint)
        cooling_setpoint.loc[winter] = np.maximum(
            cooling_setpoint.loc[winter], float(winter_heating_setpoint) + 1.0
        )
        model.sim_demand_direct(
            heating_setpoint=heating_setpoint,
            cooling_setpoint=cooling_setpoint,
        )
    return model, archetype, persons, area_m2


def _scenario_rows(model, building, year, efficiency):
    heating_load = model.detailedResults["Heating Load"]
    demand_kwh = float(heating_load.sum())
    rows = []

    def add_result(
        scenario,
        target_fuel,
        coverage=None,
        source="coverage_sensitivity",
        redpe_case=None,
        redpe_target_m3st=None,
    ):
        result = tsib.simulate_wood_stove_from_5r1c(
            model,
            fuel_energy_target_kwh=target_fuel,
            efficiency=efficiency,
        )
        rows.append(
            {
                "edificio_id": int(building["edificio_id"]),
                "commune_id": int(building["tmy_commune_id"]),
                "nombre_comuna": building["nombre_comuna"],
                "codigo_region": building["codigo_region"],
                "year": int(year),
                "episcope_archetype": building["episcope_archetype"],
                "tipo_comb_calef": building["tipo_comb_calef"],
                "heating_demand_kwh": demand_kwh,
                "scenario": scenario,
                "scenario_source": source,
                "redpe_case": redpe_case,
                "redpe_target_m3st": redpe_target_m3st,
                "useful_coverage_target": coverage,
                "efficiency": efficiency,
                "target_fuel_energy_kwh": target_fuel,
                "assigned_useful_energy_kwh": result.assigned_useful_energy_kwh,
                "assigned_fuel_energy_kwh": result.assigned_fuel_energy_kwh,
                "unallocated_fuel_energy_kwh": result.unallocated_fuel_energy_kwh,
                "unmet_heating_energy_kwh": result.unmet_heating_energy_kwh,
                "wood_mass_kg": result.wood_mass_kg,
                "wood_volume_solid_m3": result.wood_volume_solid_m3,
                "wood_volume_stere": result.wood_volume_stere,
            }
        )

    for scenario, coverage in SCENARIO_USEFUL_COVERAGE.items():
        target_fuel = demand_kwh * coverage / efficiency
        add_result(scenario, target_fuel, coverage=coverage)

    redpe_region = int(building["codigo_region"])
    for redpe_case in ("low", "mid", "high"):
        redpe = tsib.get_chile_regional_wood_consumption(redpe_region, redpe_case)
        add_result(
            f"redpe_{redpe_case}",
            float(redpe["energy_bruta_mwh_per_consumer"]) * 1000.0,
            source="REDPE_2020",
            redpe_case=redpe_case,
            redpe_target_m3st=float(redpe["consumption_m3st_per_consumer"]),
        )
    return pd.DataFrame(rows)


def main():
    args = _parse_args()
    _load_env_file(args.env_file)
    if not 0 < args.efficiency <= 1:
        raise ValueError("--efficiency must be in (0, 1].")

    engine = _create_engine()
    building = _load_building(engine, args.edificio_id)
    weather = _load_era5_weather(engine, building["tmy_commune_id"], args.year)
    model, archetype, persons, area_m2 = _build_model(building, weather)
    results = _scenario_rows(model, building, args.year, args.efficiency)

    print(f"edificio_id:       {building['edificio_id']}")
    print(f"comuna:            {building['nombre_comuna']} ({building['tmy_commune_id']})")
    print(f"archetype:         {archetype}")
    print(f"area/personas:     {area_m2:.1f} m2 / {persons}")
    print(f"weather rows:      {len(weather)} ({weather.index[0]} to {weather.index[-1]})")
    print(results.to_string(index=False, float_format=lambda value: f"{value:.3f}"))

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        results.to_csv(args.output, index=False)
        print(f"saved:             {args.output}")


if __name__ == "__main__":
    main()
