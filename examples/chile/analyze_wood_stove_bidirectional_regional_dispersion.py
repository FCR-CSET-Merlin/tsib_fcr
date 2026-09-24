# -*- coding: utf-8 -*-
"""Run the bidirectional wood-stove model for an existing 500-building sample.

The sample is the deterministic list produced by
``analyze_wood_stove_regional_dispersion.py``.  This analysis uses the causal
5R1C/wood-stove coupling, not the historical target-fuel post-processing
model, and compares the resulting annual log consumption with the REDPE
regional ranges expressed in stere cubic metres per consumer dwelling.
"""

from __future__ import annotations

import argparse
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from types import SimpleNamespace

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from sqlalchemy import text

import tsib
from examples.chile.analyze_wood_stove_regional_dispersion import (
    REGION_NAMES,
    VALID_ARCHETYPE_RE,
)
from examples.chile.validate_wood_stove_geonode import (
    DEFAULT_EFFICIENCY,
    DEFAULT_YEAR,
    _build_model,
    _create_engine,
    _load_env_file,
    _load_era5_weather,
)


GEOGRAPHIC_REGION_ORDER = [
    15,  # Arica y Parinacota
    1,   # Tarapaca
    2,   # Antofagasta
    3,   # Atacama
    4,   # Coquimbo
    5,   # Valparaiso
    13,  # RM
    6,   # O'Higgins
    7,   # Maule
    16,  # Nuble
    8,   # Biobio
    9,   # Araucania
    14,  # Los Rios
    10,  # Los Lagos
    11,  # Aysen
    12,  # Magallanes
]


DEFAULT_SAMPLE_FILE = Path(
    "outputs/chile_wood_stove_regional_dispersion_hdd12/selected_buildings.csv"
)
DEFAULT_LOGS_PER_STERE = 220.0
DEFAULT_TIMESTEP_MINUTES = 30
DEFAULT_INTERVAL_HOURS = 1.0
DEFAULT_SETPOINT_OFFSET_C = 3.0
DEFAULT_TRIGGER_DELTA_C = 8.0
DEFAULT_WIND_REFERENCE_MS = 2.0
DEFAULT_WIND_BETA = 0.10
DEFAULT_WET_BETA = 0.05
DEFAULT_MAX_H_VENT_MULTIPLIER = 1.50
HDD_BASES_C = (12.0, 14.0)
DEFAULT_HDD_REFERENCE_FILE = Path(
    "outputs/chile_hdd_reference/hdd_regional_ponderado_lena_2024.csv"
)
DEFAULT_HDD_BASE_C = 14.0
DEFAULT_HDD_BETA_WALL = 0.25
DEFAULT_HDD_BETA_WINDOW = 0.15
DEFAULT_HDD_BETA_INFILTRATION = 0.35
DEFAULT_HDD_FACTOR_MIN = 0.70
DEFAULT_HDD_FACTOR_MAX = 1.75
REGIONAL_SETPOINT_OFFSETS_C = {
    13: -1.0,  # RM
    8: 2.0,   # Biobio
    9: 3.0,   # Araucania
    14: 3.0,  # Los Rios
    10: 4.0,  # Los Lagos
    11: 5.0,  # Aysen
}


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-file", type=Path, default=DEFAULT_SAMPLE_FILE)
    parser.add_argument("--env-file", type=Path, default=None)
    parser.add_argument("--year", type=int, default=DEFAULT_YEAR)
    parser.add_argument("--efficiency", type=float, default=DEFAULT_EFFICIENCY)
    parser.add_argument(
        "--logs-per-stere", type=float, default=DEFAULT_LOGS_PER_STERE
    )
    parser.add_argument(
        "--timestep-minutes", type=int, default=DEFAULT_TIMESTEP_MINUTES
    )
    parser.add_argument(
        "--min-event-interval-hours",
        type=float,
        default=DEFAULT_INTERVAL_HOURS,
    )
    parser.add_argument(
        "--setpoint-offset-c", type=float, default=DEFAULT_SETPOINT_OFFSET_C
    )
    parser.add_argument(
        "--hardcoded-regional-offsets",
        action="store_true",
        help="Aplica los offsets regionales definidos en REGIONAL_SETPOINT_OFFSETS_C.",
    )
    parser.add_argument(
        "--trigger-delta-c", type=float, default=DEFAULT_TRIGGER_DELTA_C,
        help="Diferencia minima entre setpoint y temperatura exterior para iniciar.",
    )
    parser.add_argument(
        "--weather-exposure",
        action="store_true",
        help="Activa el ajuste temporal de H_vent por viento y humedad.",
    )
    parser.add_argument(
        "--wind-reference-ms", type=float, default=DEFAULT_WIND_REFERENCE_MS
    )
    parser.add_argument("--wind-beta", type=float, default=DEFAULT_WIND_BETA)
    parser.add_argument("--wet-beta", type=float, default=DEFAULT_WET_BETA)
    parser.add_argument(
        "--max-h-vent-multiplier",
        type=float,
        default=DEFAULT_MAX_H_VENT_MULTIPLIER,
    )
    parser.add_argument(
        "--hdd-envelope",
        action="store_true",
        help="Ajusta U e infiltracion por HDD regionales ponderados por inmuebles.",
    )
    parser.add_argument(
        "--hdd-file",
        type=Path,
        default=DEFAULT_HDD_REFERENCE_FILE,
        help="CSV aislado con HDD regionales previamente calculados.",
    )
    parser.add_argument(
        "--hdd-base-c",
        type=float,
        choices=HDD_BASES_C,
        default=DEFAULT_HDD_BASE_C,
        help="Base de grados-dia usada por el ajuste de envolvente.",
    )
    parser.add_argument(
        "--hdd-beta-wall", type=float, default=DEFAULT_HDD_BETA_WALL
    )
    parser.add_argument(
        "--hdd-beta-window", type=float, default=DEFAULT_HDD_BETA_WINDOW
    )
    parser.add_argument(
        "--hdd-beta-infiltration",
        type=float,
        default=DEFAULT_HDD_BETA_INFILTRATION,
    )
    parser.add_argument(
        "--hdd-factor-min", type=float, default=DEFAULT_HDD_FACTOR_MIN
    )
    parser.add_argument(
        "--hdd-factor-max", type=float, default=DEFAULT_HDD_FACTOR_MAX
    )
    parser.add_argument("--spinup-passes", type=int, default=1)
    parser.add_argument(
        "--workers",
        type=int,
        default=10,
        help="Procesos paralelos para las simulaciones (default: 10).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory for per-building results, regional table and figure.",
    )
    parser.add_argument(
        "--reuse-results",
        action="store_true",
        help="Recalcula HDD, tabla y grafico usando simulation_results.csv existente.",
    )
    return parser.parse_args()


def _resample_weather_to_half_hour(weather):
    """Create an explicit 30-minute weather input from hourly ERA5 values."""

    half_hour = weather.resample("30min").interpolate(method="time")
    end = weather.index[-1] + pd.Timedelta(hours=1) - pd.Timedelta(minutes=30)
    return half_hour.loc[weather.index[0] : end]


def _weighted_mean(series, weights):
    values = pd.to_numeric(series, errors="coerce").to_numpy(dtype=float)
    weights = (
        pd.to_numeric(weights, errors="coerce")
        .fillna(1.0)
        .clip(lower=1.0)
        .to_numpy(dtype=float)
    )
    valid = np.isfinite(values) & np.isfinite(weights) & (weights > 0)
    if not valid.any():
        return np.nan
    return float(np.average(values[valid], weights=weights[valid]))


def _load_redpe_ranges():
    rows = []
    for region_code in sorted(REGION_NAMES):
        try:
            low = tsib.get_chile_regional_wood_consumption(region_code, "low")
            mid = tsib.get_chile_regional_wood_consumption(region_code, "mid")
            high = tsib.get_chile_regional_wood_consumption(region_code, "high")
        except ValueError:
            continue
        rows.append(
            {
                "codigo_region": region_code,
                "region": REGION_NAMES[region_code],
                "redpe_low_m3st": float(low["consumption_m3st_per_consumer"]),
                "redpe_mid_m3st": float(mid["consumption_m3st_per_consumer"]),
                "redpe_high_m3st": float(high["consumption_m3st_per_consumer"]),
                "redpe_year": int(mid["anio"]),
            }
        )
    return pd.DataFrame(rows)


def _load_regional_hdd(engine, year, base_temperatures_c=HDD_BASES_C):
    """Calculate commune HDD weighted by the regional wood-heating stock."""

    base_temperatures_c = tuple(float(base) for base in base_temperatures_c)
    if len(base_temperatures_c) != 2:
        raise ValueError("Se requieren exactamente dos bases HDD.")
    query = text(
        """
        WITH wood_population AS (
            SELECT
                c.cut_region AS codigo_region,
                COALESCE(c.cut_comuna, e.codigo_comuna) AS commune_id,
                SUM(GREATEST(COALESCE(e.n_inmuebles, 1), 1))::double precision
                    AS wood_units
            FROM merlin_rcp.edificios AS e
            JOIN merlin_rcp.comunas_sii_cut AS c
              ON c.codigo_sii = e.codigo_comuna
            WHERE lower(trim(e.tipo_comb_calef)) = 'lena'
              AND c.cut_region BETWEEN 1 AND 16
              AND e.episcope_archetype ~ :archetype_re
              AND e.area_promedio_inmueble IS NOT NULL
              AND e.area_promedio_inmueble > 0
              AND e.longitud IS NOT NULL
              AND e.latitud IS NOT NULL
            GROUP BY c.cut_region, COALESCE(c.cut_comuna, e.codigo_comuna)
        ), daily AS (
            SELECT
                p.codigo_region,
                p.commune_id,
                p.wood_units,
                (m.timestamp_utc AT TIME ZONE 'America/Santiago')::date
                    AS local_date,
                AVG(m.tdry)::double precision AS tmean_c
            FROM wood_population AS p
            JOIN meteorology_commune.era5_hourly_comunal AS m
              ON m.commune_id = p.commune_id
            WHERE (m.timestamp_utc AT TIME ZONE 'America/Santiago')::date
                    >= :start_date
              AND (m.timestamp_utc AT TIME ZONE 'America/Santiago')::date
                    < :end_date
            GROUP BY
                p.codigo_region,
                p.commune_id,
                p.wood_units,
                (m.timestamp_utc AT TIME ZONE 'America/Santiago')::date
        ), commune_hdd AS (
            SELECT
                codigo_region,
                commune_id,
                wood_units,
                SUM(GREATEST(:hdd_base_12 - tmean_c, 0.0)) AS hdd12,
                SUM(GREATEST(:hdd_base_14 - tmean_c, 0.0)) AS hdd14
            FROM daily
            GROUP BY codigo_region, commune_id, wood_units
        )
        SELECT
            codigo_region,
            COUNT(*) AS hdd_communes,
            SUM(wood_units) AS wood_units,
            SUM(hdd12 * wood_units) / SUM(wood_units) AS hdd12_regional,
            SUM(hdd14 * wood_units) / SUM(wood_units) AS hdd14_regional
        FROM commune_hdd
        GROUP BY codigo_region
        ORDER BY codigo_region
        """
    )
    with engine.connect() as connection:
        regional = pd.read_sql_query(
            query,
            connection,
            params={
                "archetype_re": VALID_ARCHETYPE_RE,
                "start_date": f"{int(year)}-01-01",
                "end_date": f"{int(year) + 1}-01-01",
                "hdd_base_12": base_temperatures_c[0],
                "hdd_base_14": base_temperatures_c[1],
            },
        )
    if regional.empty:
        raise RuntimeError("No se pudo calcular HDD regional para el stock de lena.")
    regional["region"] = regional["codigo_region"].map(REGION_NAMES)
    return regional


def _load_hdd_envelope_parameters(path, base_temperature_c, beta_wall,
                                  beta_window, beta_infiltration,
                                  factor_min, factor_max):
    """Load the isolated HDD reference and derive bounded regional factors."""

    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo HDD: {path}")
    frame = pd.read_csv(path)
    column = f"hdd{int(base_temperature_c)}_c_day"
    required = {"codigo_region", "region", column}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(
            f"El archivo HDD no contiene las columnas requeridas: {', '.join(missing)}"
        )
    frame = frame.copy()
    frame["codigo_region"] = pd.to_numeric(frame["codigo_region"], errors="coerce")
    frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["codigo_region", column])
    frame["codigo_region"] = frame["codigo_region"].astype(int)
    frame = frame[frame["codigo_region"].isin(REGION_NAMES)]
    if frame["codigo_region"].duplicated().any():
        raise ValueError(f"El archivo HDD tiene regiones duplicadas: {path}")
    expected = set(REGION_NAMES)
    present = set(frame["codigo_region"])
    missing_regions = sorted(expected.difference(present))
    if missing_regions:
        raise ValueError(
            "El archivo HDD no contiene todas las regiones; faltan: "
            + ", ".join(str(code) for code in missing_regions)
        )
    if not np.isfinite(frame[column]).all() or (frame[column] <= 0).any():
        raise ValueError("Los HDD deben ser positivos y finitos.")
    if factor_min <= 0 or factor_max < factor_min:
        raise ValueError("Los limites de factores HDD son invalidos.")
    for name, value in {
        "beta_wall": beta_wall,
        "beta_window": beta_window,
        "beta_infiltration": beta_infiltration,
    }.items():
        if not np.isfinite(value) or value < 0:
            raise ValueError(f"{name} debe ser no negativo y finito.")

    hdd_reference = float(frame[column].median())
    parameters = {}
    for row in frame.sort_values("codigo_region").itertuples(index=False):
        hdd_value = float(getattr(row, column))
        ratio = hdd_value / hdd_reference
        parameters[int(row.codigo_region)] = {
            "hdd_base_c": float(base_temperature_c),
            "hdd_regional_c_day": hdd_value,
            "hdd_reference_c_day": hdd_reference,
            "hdd_ratio_to_reference": ratio,
            "wall_u_multiplier": float(
                np.clip(ratio ** beta_wall, factor_min, factor_max)
            ),
            "window_u_multiplier": float(
                np.clip(ratio ** beta_window, factor_min, factor_max)
            ),
            "infiltration_multiplier": float(
                np.clip(ratio ** beta_infiltration, factor_min, factor_max)
            ),
            "hdd_beta_wall": float(beta_wall),
            "hdd_beta_window": float(beta_window),
            "hdd_beta_infiltration": float(beta_infiltration),
            "hdd_factor_min": float(factor_min),
            "hdd_factor_max": float(factor_max),
        }
    return {
        "source_file": str(path),
        "base_temperature_c": float(base_temperature_c),
        "hdd_reference_c_day": hdd_reference,
        "beta_wall": float(beta_wall),
        "beta_window": float(beta_window),
        "beta_infiltration": float(beta_infiltration),
        "factor_min": float(factor_min),
        "factor_max": float(factor_max),
        "regional": parameters,
    }


def _weather_exposure_profile(model, weather, args):
    """Build a conservative effective H_vent profile from available ERA5 data."""

    columns = {str(column).lower(): column for column in weather.columns}
    wind_column = columns.get("ws", columns.get("wspd"))
    rh_column = columns.get("rh")
    tdew_column = columns.get("tdew")
    dry_column = columns.get("t") or columns.get("tdry")
    missing = [
        name
        for name, column in {
            "viento": wind_column,
            "humedad relativa": rh_column,
            "punto de rocio": tdew_column,
            "temperatura seca": dry_column,
        }.items()
        if column is None
    ]
    if missing:
        raise ValueError(
            "No se puede activar weather-exposure; faltan columnas: "
            + ", ".join(missing)
        )

    wind_ms = pd.to_numeric(weather[wind_column], errors="coerce").to_numpy(float)
    rh = pd.to_numeric(weather[rh_column], errors="coerce").to_numpy(float)
    tdew = pd.to_numeric(weather[tdew_column], errors="coerce").to_numpy(float)
    tdry = pd.to_numeric(weather[dry_column], errors="coerce").to_numpy(float)
    if not all(np.isfinite(values).all() for values in (wind_ms, rh, tdew, tdry)):
        raise ValueError("weather-exposure requiere señales meteorologicas finitas.")

    dewpoint_depression = np.maximum(tdry - tdew, 0.0)
    wet_index = np.clip((rh - 80.0) / 20.0, 0.0, 1.0)
    wet_index *= np.clip((2.0 - dewpoint_depression) / 2.0, 0.0, 1.0)
    rain_wind_index = wet_index * np.clip(wind_ms / 4.0, 0.0, 1.0)
    wind_index = (np.maximum(wind_ms, 0.0) / args.wind_reference_ms) ** 2
    multiplier = 1.0 + args.wind_beta * wind_index + args.wet_beta * rain_wind_index
    multiplier = np.clip(multiplier, 1.0, args.max_h_vent_multiplier)

    thermal_model = getattr(model, "thermalmodel", model)
    base_data = thermal_model._prepare_direct_5r1c()
    # Weather acts on infiltration only.  The prescribed ventilation term is
    # kept fixed, while the HDD envelope calibration changes the base
    # infiltration conductance through the regional model configuration.
    base_h_vent_fixed = float(base_data.get("H_vent_fixed", 0.0))
    base_h_vent_infiltration = float(
        base_data.get("H_vent_infiltration", base_data["H_vent"])
    )
    h_vent_profile = base_h_vent_fixed + base_h_vent_infiltration * multiplier
    return h_vent_profile, {
        "weather_exposure_enabled": True,
        "wind_speed_mean_ms": float(np.mean(wind_ms)),
        "wet_index_mean": float(np.mean(wet_index)),
        "rain_wind_index_mean": float(np.mean(rain_wind_index)),
        "h_vent_multiplier_mean": float(np.mean(multiplier)),
        "h_vent_multiplier_max": float(np.max(multiplier)),
        "wind_reference_ms": float(args.wind_reference_ms),
        "wind_beta": float(args.wind_beta),
        "wet_beta": float(args.wet_beta),
        "max_h_vent_multiplier": float(args.max_h_vent_multiplier),
    }


def _simulate_building(building, weather, args):
    region_code = int(building["codigo_region"])
    regional_offsets = getattr(args, "regional_setpoint_offsets", {})
    applied_setpoint_offset = float(
        regional_offsets.get(region_code, args.setpoint_offset_c)
        if getattr(args, "hardcoded_regional_offsets", False)
        else args.setpoint_offset_c
    )
    hdd_parameters = getattr(args, "hdd_envelope_parameters", {})
    hdd_factors = hdd_parameters.get("regional", {}).get(
        int(building["codigo_region"])
    )
    model, archetype, persons, area_m2 = _build_model(
        building,
        weather,
        envelope_factors=hdd_factors,
    )
    h_vent_profile = None
    exposure = {
        "weather_exposure_enabled": False,
        "wind_speed_mean_ms": np.nan,
        "wet_index_mean": np.nan,
        "rain_wind_index_mean": np.nan,
        "h_vent_multiplier_mean": 1.0,
        "h_vent_multiplier_max": 1.0,
        "wind_reference_ms": float(args.wind_reference_ms),
        "wind_beta": float(args.wind_beta),
        "wet_beta": float(args.wet_beta),
        "max_h_vent_multiplier": float(args.max_h_vent_multiplier),
    }
    if hdd_factors is None:
        hdd_factors = {}
    envelope = {
        "hdd_envelope_enabled": bool(hdd_parameters),
        "hdd_base_c": float(hdd_factors.get("hdd_base_c", np.nan)),
        "hdd_regional_c_day": float(
            hdd_factors.get("hdd_regional_c_day", np.nan)
        ),
        "hdd_reference_c_day": float(
            hdd_factors.get("hdd_reference_c_day", np.nan)
        ),
        "hdd_ratio_to_reference": float(
            hdd_factors.get("hdd_ratio_to_reference", np.nan)
        ),
        "hdd_wall_u_multiplier": float(
            hdd_factors.get("wall_u_multiplier", 1.0)
        ),
        "hdd_window_u_multiplier": float(
            hdd_factors.get("window_u_multiplier", 1.0)
        ),
        "hdd_infiltration_multiplier": float(
            hdd_factors.get("infiltration_multiplier", 1.0)
        ),
    }
    if args.weather_exposure:
        h_vent_profile, exposure = _weather_exposure_profile(model, weather, args)
    result = tsib.simulate_wood_stove_5r1c_bidirectional(
        model,
        heating_mode="wood_only",
        efficiency=args.efficiency,
        log_energy_kwh=7.5,
        logs_per_stere=args.logs_per_stere,
        heating_setpoint_offset_c=applied_setpoint_offset,
        trigger_delta_c=args.trigger_delta_c,
        h_vent_profile=h_vent_profile,
        timestep_minutes=args.timestep_minutes,
        min_event_interval_hours=args.min_event_interval_hours,
        spinup_passes=args.spinup_passes,
    )
    return {
        "edificio_id": int(building["edificio_id"]),
        "regional_sample_rank": int(building["regional_sample_rank"]),
        "codigo_region": int(building["codigo_region"]),
        "region": REGION_NAMES[int(building["codigo_region"])],
        "codigo_comuna": int(building["codigo_comuna"]),
        "tmy_commune_id": int(building["tmy_commune_id"]),
        "nombre_comuna": building["nombre_comuna"],
        "episcope_archetype": building["episcope_archetype"],
        "area_promedio_inmueble_m2": float(building["area_promedio_inmueble"]),
        "n_inmuebles": max(int(round(float(building["n_inmuebles"]))), 1),
        "sample_expansion_weight": float(building["sample_expansion_weight"]),
        "wood_inmuebles_regional": float(building["wood_inmuebles_regional"]),
        "reference_setpoint_c": float(
            result.detailed_results["Heating Setpoint"].sub(
                applied_setpoint_offset
            ).mean()
        ),
        "applied_setpoint_c": float(
            result.detailed_results["Heating Setpoint"].mean()
        ),
        "efficiency": float(result.efficiency),
        "timestep_minutes": float(result.dt_hours * 60.0),
        "min_event_interval_hours": float(
            result.scenario_parameters["min_event_interval_hours"]
        ),
        "heating_setpoint_offset_c": float(
            result.scenario_parameters["heating_setpoint_offset_c"]
        ),
        "regional_setpoint_offset_c": applied_setpoint_offset,
        "trigger_delta_c": float(result.scenario_parameters["trigger_delta_c"]),
        "wood_logs": float(result.wood_logs_burned),
        "wood_m3st": float(result.wood_logs_burned / args.logs_per_stere),
        "fuel_energy_kwh": float(result.fuel_energy_consumed_kwh),
        "useful_wood_energy_kwh": float(result.wood_useful_energy_kwh),
        "event_count": int(result.event_count),
        "unmet_heating_energy_kwh": float(result.unmet_heating_energy_kwh),
        "overheating_degree_hours": float(result.overheating_degree_hours),
        "building_year": int(archetype["building_year"]),
        "building_type": archetype["building_type"],
        "material": archetype["material"],
        "thermal_zone": archetype["thermal_zone"],
        "model_persons": int(persons),
        "model_area_m2": float(area_m2),
        "weather_rows": int(len(weather)),
        **envelope,
        **exposure,
    }


def _simulate_commune_group(task):
    """Simulate all selected buildings sharing one communal weather series."""

    commune_id, buildings, settings = task
    args = SimpleNamespace(**settings)
    rows = []
    errors = []
    engine = None
    try:
        # Each process owns its SQLAlchemy engine; engines/connections are not
        # shared across process boundaries.
        engine = _create_engine()
        weather_hourly = _load_era5_weather(engine, int(commune_id), args.year)
        weather = _resample_weather_to_half_hour(weather_hourly)
    except Exception as exc:
        for building in buildings:
            errors.append(
                {
                    "edificio_id": int(building["edificio_id"]),
                    "codigo_region": int(building["codigo_region"]),
                    "tmy_commune_id": int(commune_id),
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
            )
        if engine is not None:
            engine.dispose()
        return rows, errors

    try:
        for building in buildings:
            try:
                rows.append(_simulate_building(building, weather, args))
            except Exception as exc:  # retain failures for audit
                errors.append(
                    {
                        "edificio_id": int(building["edificio_id"]),
                        "codigo_region": int(building["codigo_region"]),
                        "tmy_commune_id": int(commune_id),
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
    finally:
        engine.dispose()
    return rows, errors


def _regional_comparison(results, redpe, regional_hdd=None):
    rows = []
    for region_code, group in results.groupby("codigo_region", sort=True):
        volume = group["wood_m3st"]
        redpe_row = redpe[redpe["codigo_region"] == int(region_code)]
        if redpe_row.empty:
            redpe_values = {
                "redpe_low_m3st": np.nan,
                "redpe_mid_m3st": np.nan,
                "redpe_high_m3st": np.nan,
                "redpe_year": np.nan,
            }
        else:
            redpe_values = redpe_row.iloc[0].to_dict()
        low = redpe_values["redpe_low_m3st"]
        high = redpe_values["redpe_high_m3st"]
        within = ((volume >= low) & (volume <= high)).mean() if np.isfinite(low) else np.nan
        weighted_mean = _weighted_mean(volume, group["n_inmuebles"])
        rows.append(
            {
                "codigo_region": int(region_code),
                "region": REGION_NAMES[int(region_code)],
                "n_simulations": int(len(group)),
                "n_inmuebles_sampled": int(group["n_inmuebles"].sum()),
                "wood_m3st_min": float(volume.min()),
                "wood_m3st_p10": float(volume.quantile(0.10)),
                "wood_m3st_median": float(volume.median()),
                "wood_m3st_weighted_mean": weighted_mean,
                "wood_m3st_p90": float(volume.quantile(0.90)),
                "wood_m3st_max": float(volume.max()),
                "wood_m3st_std": float(volume.std(ddof=1)) if len(volume) > 1 else 0.0,
                "wood_m3st_cv": float(volume.std(ddof=1) / volume.mean()) if len(volume) > 1 and volume.mean() else np.nan,
                **redpe_values,
                "share_inside_redpe_range": float(within) if np.isfinite(within) else np.nan,
                "weighted_mean_to_redpe_mid": (
                    weighted_mean / redpe_values["redpe_mid_m3st"]
                    if np.isfinite(redpe_values["redpe_mid_m3st"])
                    else np.nan
                ),
                "weighted_mean_relative_error": (
                    weighted_mean / redpe_values["redpe_mid_m3st"] - 1.0
                    if np.isfinite(redpe_values["redpe_mid_m3st"])
                    else np.nan
                ),
            }
        )
    comparison = pd.DataFrame(rows)
    if regional_hdd is not None:
        hdd_columns = [
            "codigo_region",
            "hdd_communes",
            "wood_units",
            "hdd12_regional",
            "hdd14_regional",
        ]
        comparison = comparison.merge(
            regional_hdd[hdd_columns],
            on="codigo_region",
            how="left",
            validate="one_to_one",
        )
    return comparison


def _write_plot(results, comparison, output_path, args):
    ordered = (
        comparison.set_index("codigo_region")
        .reindex(GEOGRAPHIC_REGION_ORDER)
        .dropna(subset=["region"])
        .reset_index()
    )
    labels = ordered["region"].tolist()
    data = [
        results.loc[results["codigo_region"] == code, "wood_m3st"].to_numpy()
        for code in ordered["codigo_region"]
    ]
    x = np.arange(1, len(data) + 1)
    fig, ax = plt.subplots(figsize=(16, 8.5), constrained_layout=True)
    box = ax.boxplot(
        data,
        positions=x,
        widths=0.55,
        patch_artist=True,
        showfliers=False,
        medianprops={"color": "#111111", "linewidth": 1.5},
        boxprops={"facecolor": "#8ecae6", "edgecolor": "#277da1"},
        whiskerprops={"color": "#277da1"},
        capprops={"color": "#277da1"},
    )
    for patch in box["boxes"]:
        patch.set_alpha(0.75)

    for xpos, row in zip(x, ordered.itertuples(index=False)):
        if np.isfinite(row.redpe_low_m3st):
            ax.vlines(
                xpos,
                row.redpe_low_m3st,
                row.redpe_high_m3st,
                color="#d62828",
                linewidth=5,
                alpha=0.85,
                zorder=4,
            )
            ax.scatter(
                xpos,
                row.redpe_mid_m3st,
                color="#8b0000",
                marker="D",
                s=42,
                zorder=5,
            )
        ax.scatter(
            xpos,
            row.wood_m3st_weighted_mean,
            color="#111111",
            marker="x",
            s=48,
            zorder=5,
        )

    ax.set_xticks(x, labels, rotation=45, ha="right")
    ax.set_ylabel("Consumo anual de leña [m³ estéreo/año]")
    ax.set_xlabel("Región")
    ax.set_title(
        "Dispersión regional del consumo simulado de leña vs. rangos REDPE\n"
        f"500 edificios · {args.year} · paso {args.timestep_minutes} min · "
        f"intervalo {args.min_event_interval_hours:g} h · setpoint +{args.setpoint_offset_c:g} °C · "
        f"disparador exterior {args.trigger_delta_c:g} °C"
        + (" · viento/humedad en infiltración" if args.weather_exposure else "")
        + (" · envolvente calibrada con HDD" if args.hdd_envelope else "")
        + (" · offsets regionales hardcodeados" if args.hardcoded_regional_offsets else "")
    )
    ax.grid(axis="y", alpha=0.25)
    handles = [
        Line2D([0], [0], color="#8ecae6", marker="s", markersize=10, linewidth=8, label="Simulación: P10–P90 / mediana"),
        Line2D([0], [0], color="#d62828", linewidth=5, label="REDPE: rango bajo–alto"),
        Line2D([0], [0], color="#8b0000", marker="D", linestyle="None", label="REDPE: punto medio"),
        Line2D([0], [0], color="#111111", marker="x", linestyle="None", markersize=8, label="Simulación: media ponderada"),
    ]
    hdd_axis = None
    if "hdd12_regional" in ordered or "hdd14_regional" in ordered:
        hdd_axis = ax.twinx()
        hdd_series = (
            ("hdd12_regional", "#f77f00", "o", "HDD12 ponderado por inmuebles a leña"),
            ("hdd14_regional", "#8338ec", "^", "HDD14 ponderado por inmuebles a leña"),
        )
        for column, color, marker, label in hdd_series:
            if column not in ordered:
                continue
            hdd_axis.plot(
                x,
                ordered[column].to_numpy(dtype=float),
                color=color,
                marker=marker,
                linewidth=2,
                markersize=5,
                label=label,
                zorder=6,
            )
            handles.append(
                Line2D([0], [0], color=color, marker=marker, linewidth=2, label=label)
            )
        hdd_axis.set_ylabel("Grados día de calefacción [°C·día/año]")
        hdd_axis.grid(False)
    ax.legend(
        handles=handles,
        loc="upper left",
        frameon=True,
    )
    fig.savefig(output_path, dpi=170)
    plt.close(fig)


def _write_markdown(comparison, output_path, args):
    view = (
        comparison.set_index("codigo_region")
        .reindex(GEOGRAPHIC_REGION_ORDER)
        .dropna(subset=["region"])
        .reset_index()
    )
    for column in view.columns:
        if pd.api.types.is_float_dtype(view[column]):
            view[column] = view[column].map(
                lambda value: "—" if not np.isfinite(value) else f"{value:.2f}"
            )
    columns = [
        "region",
        "n_simulations",
        "wood_m3st_p10",
        "wood_m3st_median",
        "wood_m3st_weighted_mean",
        "wood_m3st_p90",
        "redpe_low_m3st",
        "redpe_mid_m3st",
        "redpe_high_m3st",
        "share_inside_redpe_range",
        "weighted_mean_relative_error",
        "hdd12_regional",
        "hdd14_regional",
        "hdd_communes",
    ]
    labels = {
        "region": "Región",
        "n_simulations": "n",
        "wood_m3st_p10": "Sim P10 (m³ st/a)",
        "wood_m3st_median": "Sim mediana",
        "wood_m3st_weighted_mean": "Sim media ponderada",
        "wood_m3st_p90": "Sim P90",
        "redpe_low_m3st": "REDPE bajo",
        "redpe_mid_m3st": "REDPE medio",
        "redpe_high_m3st": "REDPE alto",
        "share_inside_redpe_range": "% dentro rango",
        "weighted_mean_relative_error": "Error relativo media",
        "hdd12_regional": "HDD12 ponderado",
        "hdd14_regional": "HDD14 ponderado",
        "hdd_communes": "Comunas HDD",
    }
    with output_path.open("w", encoding="utf-8") as handle:
        handle.write("# Comparación regional: simulación bidireccional vs REDPE\n\n")
        handle.write(
            f"Parámetros: {len(comparison)} regiones, año {args.year}, "
            f"paso {args.timestep_minutes} min, intervalo {args.min_event_interval_hours:g} h, "
            f"setpoint +{args.setpoint_offset_c:g} °C, disparador exterior "
            f"{args.trigger_delta_c:g} °C, eficiencia {args.efficiency:.2f}, "
            f"220 leños = 1 m³ estéreo.\n\n"
        )
        if args.hardcoded_regional_offsets:
            handle.write(
                "Offsets regionales hardcodeados: RM −1 °C, Biobío +2 °C, "
                "Araucanía +3 °C, Los Ríos +3 °C, Los Lagos +4 °C y Aysén "
                "+4 °C; las demás regiones usan el offset global.\n\n"
            )
        handle.write(
            "REDPE corresponde a rangos anuales por vivienda consumidora y sólo "
            "tiene filas para nueve regiones. La caja simulada representa la "
            "dispersión P10–P90; la media se pondera por `n_inmuebles`. Los HDD "
            "son medias regionales ponderadas por las unidades habitacionales que "
            "declaran leña en cada comuna. "
            + (
                "La corrida aplica un multiplicador temporal sólo a la infiltración usando "
                "velocidad del viento y un proxy de humedad `RH + (Tdry-Tdew)`.\n\n"
                if args.weather_exposure
                else "\n\n"
            )
        )
        if args.hdd_envelope:
            handle.write(
                "La envolvente aplica multiplicadores regionales acotados a U de "
                f"muros/ventanas e infiltración usando HDD{int(args.hdd_base_c)}; "
                f"la referencia es la mediana regional "
                f"({args.hdd_factor_min:.2f}–{args.hdd_factor_max:.2f} de factor).\n\n"
            )
        handle.write(view[columns].rename(columns=labels).to_markdown(index=False))
        handle.write("\n")


def _write_analysis_outputs(results, args, requested_buildings, failed_simulations):
    """Rebuild regional HDD, comparison files and figure from simulations."""

    _load_env_file(args.env_file)
    engine = _create_engine()
    try:
        regional_hdd = _load_regional_hdd(engine, args.year)
    finally:
        engine.dispose()

    regional_hdd.to_csv(
        args.output_dir / "regional_hdd_weighted_by_wood_units.csv", index=False
    )
    redpe = _load_redpe_ranges()
    redpe.to_csv(args.output_dir / "redpe_reference_ranges.csv", index=False)
    comparison = _regional_comparison(results, redpe, regional_hdd)
    comparison.to_csv(args.output_dir / "regional_consumption_comparison.csv", index=False)
    _write_markdown(comparison, args.output_dir / "regional_consumption_comparison.md", args)
    _write_plot(
        results,
        comparison,
        args.output_dir / "regional_consumption_vs_redpe.png",
        args,
    )

    summary = {
        "sample_file": str(args.sample_file),
        "requested_buildings": int(requested_buildings),
        "successful_simulations": int(len(results)),
        "failed_simulations": int(failed_simulations),
        "year": int(args.year),
        "efficiency": float(args.efficiency),
        "logs_per_stere": float(args.logs_per_stere),
        "timestep_minutes": int(args.timestep_minutes),
        "min_event_interval_hours": float(args.min_event_interval_hours),
        "heating_setpoint_offset_c": float(args.setpoint_offset_c),
        "hardcoded_regional_offsets": bool(args.hardcoded_regional_offsets),
        "regional_setpoint_offsets_c": {
            str(code): float(offset)
            for code, offset in args.regional_setpoint_offsets.items()
        },
        "trigger_delta_c": float(args.trigger_delta_c),
        "weather_exposure": bool(args.weather_exposure),
        "wind_reference_ms": float(args.wind_reference_ms),
        "wind_beta": float(args.wind_beta),
        "wet_beta": float(args.wet_beta),
        "max_h_vent_multiplier": float(args.max_h_vent_multiplier),
        "hdd_envelope": bool(args.hdd_envelope),
        "hdd_file": str(args.hdd_file),
        "hdd_base_c": float(args.hdd_base_c),
        "hdd_reference_c_day": (
            float(args.hdd_envelope_parameters["hdd_reference_c_day"])
            if getattr(args, "hdd_envelope_parameters", {})
            else None
        ),
        "hdd_beta_wall": float(args.hdd_beta_wall),
        "hdd_beta_window": float(args.hdd_beta_window),
        "hdd_beta_infiltration": float(args.hdd_beta_infiltration),
        "hdd_factor_min": float(args.hdd_factor_min),
        "hdd_factor_max": float(args.hdd_factor_max),
        "spinup_passes": int(args.spinup_passes),
        "redpe_regions": int(len(redpe)),
        "hdd_bases_c": list(HDD_BASES_C),
        "hdd_weighting": "n_inmuebles de registros elegibles con tipo_comb_calef=lena",
        "conversion_note": "220 logs = 1 m3 stere",
    }
    (args.output_dir / "run_summary.json").write_text(
        pd.Series(summary).to_json(indent=2), encoding="utf-8"
    )
    return summary, comparison


def main():
    args = _parse_args()
    if not args.sample_file.exists():
        raise FileNotFoundError(f"No existe la muestra: {args.sample_file}")
    if args.logs_per_stere <= 0 or args.timestep_minutes <= 0:
        raise ValueError("logs-per-stere y timestep-minutes deben ser positivos.")
    if args.min_event_interval_hours < 0 or args.spinup_passes < 1:
        raise ValueError("intervalo no negativo y spinup-passes positivo requeridos.")
    if args.trigger_delta_c < 0:
        raise ValueError("trigger-delta-c debe ser no negativo.")
    if args.wind_reference_ms <= 0 or args.wind_beta < 0 or args.wet_beta < 0:
        raise ValueError("parametros de viento/humedad invalidos.")
    if args.max_h_vent_multiplier < 1:
        raise ValueError("max-h-vent-multiplier debe ser al menos 1.")
    if (
        args.hdd_beta_wall < 0
        or args.hdd_beta_window < 0
        or args.hdd_beta_infiltration < 0
        or args.hdd_factor_min <= 0
        or args.hdd_factor_max < args.hdd_factor_min
    ):
        raise ValueError("parametros de envolvente HDD invalidos.")
    if args.workers < 1:
        raise ValueError("workers debe ser positivo.")

    args.hdd_envelope_parameters = (
        _load_hdd_envelope_parameters(
            args.hdd_file,
            args.hdd_base_c,
            args.hdd_beta_wall,
            args.hdd_beta_window,
            args.hdd_beta_infiltration,
            args.hdd_factor_min,
            args.hdd_factor_max,
        )
        if args.hdd_envelope
        else {}
    )
    args.regional_setpoint_offsets = dict(REGIONAL_SETPOINT_OFFSETS_C)

    buildings = pd.read_csv(args.sample_file)
    required = {
        "edificio_id",
        "regional_sample_rank",
        "codigo_region",
        "codigo_comuna",
        "tmy_commune_id",
        "nombre_comuna",
        "episcope_archetype",
        "area_promedio_inmueble",
        "n_inmuebles",
        "sample_expansion_weight",
        "wood_inmuebles_regional",
    }
    missing = sorted(required.difference(buildings.columns))
    if missing:
        raise ValueError("La muestra no contiene: " + ", ".join(missing))
    if buildings["edificio_id"].nunique() != len(buildings):
        raise ValueError("La muestra contiene edificio_id duplicados.")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.reuse_results:
        results_path = args.output_dir / "simulation_results.csv"
        if not results_path.exists():
            raise FileNotFoundError(
                f"No existe el resultado que se quiere reutilizar: {results_path}"
            )
        results = pd.read_csv(results_path)
        errors_path = args.output_dir / "simulation_errors.csv"
        failed_simulations = (
            int(len(pd.read_csv(errors_path))) if errors_path.exists() else 0
        )
        summary, _ = _write_analysis_outputs(
            results,
            args,
            requested_buildings=len(results) + failed_simulations,
            failed_simulations=failed_simulations,
        )
        print(pd.DataFrame([summary]).to_string(index=False))
        return

    _load_env_file(args.env_file)
    rows = []
    errors = []
    total = len(buildings)
    settings = {
        "year": args.year,
        "efficiency": args.efficiency,
        "logs_per_stere": args.logs_per_stere,
        "timestep_minutes": args.timestep_minutes,
        "min_event_interval_hours": args.min_event_interval_hours,
        "setpoint_offset_c": args.setpoint_offset_c,
        "hardcoded_regional_offsets": args.hardcoded_regional_offsets,
        "regional_setpoint_offsets": args.regional_setpoint_offsets,
        "trigger_delta_c": args.trigger_delta_c,
        "weather_exposure": args.weather_exposure,
        "wind_reference_ms": args.wind_reference_ms,
        "wind_beta": args.wind_beta,
        "wet_beta": args.wet_beta,
        "max_h_vent_multiplier": args.max_h_vent_multiplier,
        "hdd_envelope_parameters": args.hdd_envelope_parameters,
        "spinup_passes": args.spinup_passes,
    }
    tasks = [
        (int(commune_id), group.to_dict("records"), settings)
        for commune_id, group in buildings.groupby("tmy_commune_id", sort=True)
    ]
    worker_count = min(args.workers, len(tasks))
    context = mp.get_context("spawn")
    print(
        f"Ejecutando {total} edificios en {worker_count} procesos y "
        f"{len(tasks)} grupos meteorológicos.",
        flush=True,
    )
    with ProcessPoolExecutor(
        max_workers=worker_count,
        mp_context=context,
    ) as pool:
        future_tasks = {
            pool.submit(_simulate_commune_group, task): task for task in tasks
        }
        completed = 0
        for future in as_completed(future_tasks):
            commune_id, group, _ = future_tasks[future]
            try:
                group_rows, group_errors = future.result()
            except Exception as exc:
                group_rows = []
                group_errors = [
                    {
                        "edificio_id": int(building["edificio_id"]),
                        "codigo_region": int(building["codigo_region"]),
                        "tmy_commune_id": int(commune_id),
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                    for building in group
                ]
            rows.extend(group_rows)
            errors.extend(group_errors)
            completed += len(group)
            print(
                f"Procesados {completed}/{total} "
                f"(comuna meteorológica {commune_id})",
                flush=True,
            )

    results = pd.DataFrame(rows).sort_values(["codigo_region", "regional_sample_rank"])
    errors_frame = pd.DataFrame(errors)
    if errors:
        errors_frame.to_csv(args.output_dir / "simulation_errors.csv", index=False)
    elif not errors_frame.empty:
        errors_frame.to_csv(args.output_dir / "simulation_errors.csv", index=False)
    results.to_csv(args.output_dir / "simulation_results.csv", index=False)

    summary, _ = _write_analysis_outputs(
        results,
        args,
        requested_buildings=total,
        failed_simulations=len(errors),
    )
    print(pd.DataFrame([summary]).to_string(index=False))


if __name__ == "__main__":
    main()
