# -*- coding: utf-8 -*-
"""Estimate regional dispersion of Chilean wood-stove simulations.

The script selects a deterministic, regionally proportional sample of
wood-heating building records from ``merlin_rcp.edificios`` (500 records by
default), joins each record to its communal ERA5 series, and runs the direct
5R1C model from tsib_fcr.

The comparable scenario across all regions is ``coverage_mid``: 75% useful
heating coverage with the configured stove efficiency.  For regions covered
by the REDPE 2020 table, the script also evaluates ``redpe_mid`` using the
regional mid-range target per consumer dwelling.  The latter is a reference
fuel target and is intentionally kept separate from the coverage sensitivity.

With ``--apply-climate-severity``, the southern and austral regions apply a
moderated construction-loss proxy derived from annual heating degree days
(HDD12).  This is deliberately separate from the base run because the 5R1C
model already receives the hourly outdoor temperature; the HDD factor is only
a proxy for omitted wind/rain exposure and unobserved envelope quality.

Credentials are read from ``GEONODE_*`` environment variables.  An optional
env file can be supplied for local development; it is never written to the
repository.

Example from the repository root::

    PYTHONPATH=. python examples/chile/analyze_wood_stove_regional_dispersion.py \
        --env-file /home/pca/merlin/geonode_connection/.env \
        --year 2024 \
        --output-dir /tmp/wood_stove_regional_dispersion
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

import tsib
from examples.chile.validate_wood_stove_geonode import (
    DEFAULT_EFFICIENCY,
    DEFAULT_YEAR,
    _build_model,
    _create_engine,
    _load_env_file,
    _load_era5_weather,
)


REGION_NAMES = {
    1: "Tarapaca",
    2: "Antofagasta",
    3: "Atacama",
    4: "Coquimbo",
    5: "Valparaiso",
    6: "O'Higgins",
    7: "Maule",
    8: "Biobio",
    9: "Araucania",
    10: "Los Lagos",
    11: "Aysen",
    12: "Magallanes",
    13: "RM",
    14: "Los Rios",
    15: "Arica y Parinacota",
    16: "Nuble",
}

VALID_ARCHETYPE_RE = (
    r"^CL\.(SFH|MFH|AB)\.(preRT|RT1|RT2|CEV|post2021)\."
    r"(adobe|hor|lad|mad|met|prefab)\.[A-I]$"
)
ERROR_COLUMNS = [
    "edificio_id",
    "codigo_region",
    "codigo_comuna",
    "tmy_commune_id",
    "error_type",
    "error",
]
SEVERITY_REGIONS = {9, 10, 11, 12, 14}
HDD_REFERENCE_REGION = 9
DEFAULT_HDD_BASE_C = 12.0
HDD_WALL_EXPONENT = 0.20
HDD_WINDOW_EXPONENT = 0.20
HDD_INFILTRATION_EXPONENT = 0.35
BASE_WALL_U_MULTIPLIER = 1.10
BASE_WINDOW_U_MULTIPLIER = 1.08
BASE_INFILTRATION_MULTIPLIER = 1.20


def _parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=DEFAULT_YEAR)
    sampling_group = parser.add_mutually_exclusive_group()
    sampling_group.add_argument(
        "--total-samples",
        type=int,
        default=500,
        help=(
            "Total de registros seleccionados proporcionalmente a las unidades "
            "con calefaccion a lena (default: 500)."
        ),
    )
    sampling_group.add_argument(
        "--samples-per-region",
        type=int,
        default=None,
        help=(
            "Compatibilidad: fija la misma cantidad de registros por region "
            "y desactiva la asignacion proporcional."
        ),
    )
    parser.add_argument(
        "--minimum-samples-per-region",
        type=int,
        default=10,
        help="Piso regional cuando se usa --total-samples (default: 10).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=2024,
        help="Semilla para la muestra determinista en PostgreSQL.",
    )
    parser.add_argument("--efficiency", type=float, default=DEFAULT_EFFICIENCY)
    parser.add_argument(
        "--apply-climate-severity",
        action="store_true",
        help=(
            "Aplica multiplicadores de U e infiltracion derivados de HDD12 "
            "en Araucania, Los Rios, Los Lagos, Aysen y Magallanes."
        ),
    )
    parser.add_argument(
        "--hdd-base-c",
        type=float,
        default=DEFAULT_HDD_BASE_C,
        help="Temperatura base de grados-dia de calefaccion (default: 12 C).",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="Archivo local con asignaciones GEONODE_*; nunca se escribe.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directorio donde se guardan resultados, resumen y errores.",
    )
    args = parser.parse_args()
    sample_count = (
        args.samples_per_region
        if args.samples_per_region is not None
        else args.total_samples
    )
    if sample_count <= 0:
        parser.error("el numero de muestras debe ser mayor que cero.")
    if args.minimum_samples_per_region <= 0:
        parser.error("--minimum-samples-per-region debe ser mayor que cero.")
    if not 0 < args.efficiency <= 1:
        parser.error("--efficiency debe estar en (0, 1].")
    if not 0 < args.hdd_base_c < 30:
        parser.error("--hdd-base-c debe estar entre 0 y 30 C.")
    return args


def _allocate_sample_counts(
    population, total_samples, *, minimum_samples_per_region=10
):
    """Allocate a total sample proportionally to regional wood units.

    ``wood_share_regional`` describes the prevalence of wood heating relative
    to the eligible regional stock.  The allocation itself uses the absolute
    number of wood-heated units, because the simulation estimates the wood
    consumer population and not only the prevalence of the fuel.
    """
    required = {
        "codigo_region",
        "total_inmuebles_regional",
        "wood_inmuebles_regional",
        "wood_records_regional",
    }
    missing = required.difference(population.columns)
    if missing:
        raise ValueError(
            "population is missing columns: " + ", ".join(sorted(missing))
        )
    if int(total_samples) <= 0:
        raise ValueError("total_samples must be greater than zero.")
    if int(minimum_samples_per_region) <= 0:
        raise ValueError("minimum_samples_per_region must be greater than zero.")

    allocation = population.copy()
    numeric_columns = [
        "total_inmuebles_regional",
        "wood_inmuebles_regional",
        "wood_records_regional",
    ]
    for column in numeric_columns:
        allocation[column] = pd.to_numeric(allocation[column], errors="coerce").fillna(0.0)
    allocation = allocation[
        (allocation["wood_inmuebles_regional"] > 0)
        & (allocation["wood_records_regional"] > 0)
    ].copy()
    if allocation.empty:
        raise RuntimeError("No hay regiones elegibles con inmuebles a lena.")

    requested = int(total_samples)
    available_records = int(allocation["wood_records_regional"].sum())
    if requested > available_records:
        raise ValueError(
            f"Se solicitaron {requested} muestras, pero solo hay "
            f"{available_records} registros de leña elegibles."
        )
    minimum = int(minimum_samples_per_region)
    minimum_required = minimum * len(allocation)
    if requested < minimum_required:
        raise ValueError(
            f"Se solicitaron {requested} muestras, pero se requieren al menos "
            f"{minimum_required} para mantener {minimum} por region."
        )

    allocation = allocation.sort_values("codigo_region").reset_index(drop=True)
    wood_units = allocation["wood_inmuebles_regional"].to_numpy(dtype=float)
    weights = wood_units / wood_units.sum()
    capacities = allocation["wood_records_regional"].to_numpy(dtype=int)
    minimum = int(minimum_samples_per_region)
    if (capacities < minimum).any():
        constrained = allocation.loc[
            allocation["wood_records_regional"] < minimum, "codigo_region"
        ].astype(int).tolist()
        raise ValueError(
            f"Las regiones {constrained} no tienen {minimum} registros de lena "
            "elegibles; reduzca el minimo regional o revise el filtro."
        )
    quotas = np.minimum(
        np.full(len(allocation), minimum, dtype=int),
        capacities,
    )
    extra_capacity = capacities - quotas
    remaining = requested - int(quotas.sum())
    extra_target = remaining * weights
    extra = np.minimum(np.floor(extra_target).astype(int), extra_capacity)
    quotas += extra

    # Largest-remainder allocation after guaranteeing one sample per region
    # and respecting the number of available eligible records.
    while int(quotas.sum()) < requested:
        deficits = extra_target - extra
        deficits[quotas >= capacities] = -np.inf
        selected = int(np.argmax(deficits))
        if not np.isfinite(deficits[selected]):
            # This can only happen when rounding/capacity constraints leave a
            # remainder.  Select the region with most remaining capacity and
            # largest population to keep the result deterministic.
            candidates = np.flatnonzero(quotas < capacities)
            if len(candidates) == 0:
                raise RuntimeError("No quedan registros para completar la cuota.")
            selected = int(
                candidates[
                    np.argmax(
                        wood_units[candidates]
                        / np.maximum(capacities[candidates] - quotas[candidates], 1)
                    )
                ]
            )
        quotas[selected] += 1
        extra[selected] += 1

    allocation["wood_share_regional"] = np.divide(
        allocation["wood_inmuebles_regional"],
        allocation["total_inmuebles_regional"],
        out=np.zeros(len(allocation), dtype=float),
        where=allocation["total_inmuebles_regional"].to_numpy(dtype=float) > 0,
    )
    allocation["sampling_weight_wood_inmuebles"] = weights
    allocation["requested_samples"] = quotas
    return allocation


def _load_regional_population(engine):
    """Return eligible regional dwelling counts and wood-heating prevalence."""
    query = text(
        """
        SELECT
            c.cut_region AS codigo_region,
            SUM(GREATEST(COALESCE(e.n_inmuebles, 1), 1)) AS total_inmuebles_regional,
            SUM(
                CASE
                    WHEN lower(trim(e.tipo_comb_calef)) = 'lena'
                    THEN GREATEST(COALESCE(e.n_inmuebles, 1), 1)
                    ELSE 0
                END
            ) AS wood_inmuebles_regional,
            COUNT(*) AS total_records_regional,
            COUNT(*) FILTER (
                WHERE lower(trim(e.tipo_comb_calef)) = 'lena'
            ) AS wood_records_regional
        FROM merlin_rcp.edificios AS e
        JOIN merlin_rcp.comunas_sii_cut AS c
          ON c.codigo_sii = e.codigo_comuna
        WHERE c.cut_region BETWEEN 1 AND 16
          AND e.episcope_archetype ~ :archetype_re
          AND e.area_promedio_inmueble IS NOT NULL
          AND e.area_promedio_inmueble > 0
          AND e.longitud IS NOT NULL
          AND e.latitud IS NOT NULL
        GROUP BY c.cut_region
        ORDER BY c.cut_region
        """
    )
    with engine.connect() as connection:
        population = pd.read_sql_query(
            query,
            connection,
            params={"archetype_re": VALID_ARCHETYPE_RE},
        )
    if population.empty:
        raise RuntimeError("No se encontro stock regional elegible.")
    return population


def _load_sampled_buildings(
    engine,
    total_samples,
    seed,
    *,
    samples_per_region=None,
    minimum_samples_per_region=10,
):
    """Select a reproducible sample with a regional wood-population quota."""
    population = _load_regional_population(engine)
    if samples_per_region is not None:
        allocation = population[
            population["wood_records_regional"] > 0
        ].copy()
        allocation["requested_samples"] = int(samples_per_region)
        allocation["wood_share_regional"] = np.divide(
            allocation["wood_inmuebles_regional"],
            allocation["total_inmuebles_regional"],
            out=np.zeros(len(allocation), dtype=float),
            where=allocation["total_inmuebles_regional"].to_numpy(dtype=float) > 0,
        )
        allocation["sampling_weight_wood_inmuebles"] = np.nan
    else:
        allocation = _allocate_sample_counts(
            population,
            total_samples,
            minimum_samples_per_region=minimum_samples_per_region,
        )

    quota_values = ", ".join(
        f"({int(row.codigo_region)}, {int(row.requested_samples)})"
        for row in allocation.itertuples(index=False)
    )
    query = text(
        f"""
        WITH regional_quota(codigo_region, sample_quota) AS (
            VALUES {quota_values}
        ), candidates AS (
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
                e.tipo_comb_calef,
                row_number() OVER (
                    PARTITION BY c.cut_region, e.codigo_comuna
                    ORDER BY md5(e.edificio_id::text || ':' || CAST(:seed AS text)), e.edificio_id
                ) AS commune_rank,
                md5(
                    c.cut_region::text || ':' || e.edificio_id::text || ':' || CAST(:seed AS text)
                ) AS sample_order
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
        ), ranked AS (
            SELECT
                candidates.*,
                row_number() OVER (
                    PARTITION BY codigo_region
                    ORDER BY commune_rank, sample_order, edificio_id
                ) AS regional_sample_rank
            FROM candidates
        )
        SELECT ranked.*, quota.sample_quota
        FROM ranked
        JOIN regional_quota AS quota
          ON quota.codigo_region = ranked.codigo_region
        WHERE regional_sample_rank <= quota.sample_quota
        ORDER BY codigo_region, regional_sample_rank
        """
    )
    with engine.connect() as connection:
        buildings = pd.read_sql_query(
            query,
            connection,
            params={
                "seed": int(seed),
                "archetype_re": VALID_ARCHETYPE_RE,
            },
        )
    if buildings.empty:
        raise RuntimeError("No se encontraron inmuebles con calefaccion a lena.")
    buildings = buildings.merge(
        allocation[
            [
                "codigo_region",
                "total_inmuebles_regional",
                "wood_inmuebles_regional",
                "total_records_regional",
                "wood_records_regional",
                "wood_share_regional",
                "sampling_weight_wood_inmuebles",
                "requested_samples",
            ]
        ],
        on="codigo_region",
        how="left",
        validate="many_to_one",
    )
    buildings["sample_expansion_weight"] = (
        buildings["wood_inmuebles_regional"]
        / buildings["requested_samples"]
    )
    return buildings


def _load_weather_cache(engine, buildings, year):
    """Load each communal weather series once for the selected sample."""
    weather_cache = {}
    commune_ids = sorted(buildings["tmy_commune_id"].dropna().astype(int).unique())
    for position, commune_id in enumerate(commune_ids, start=1):
        print(f"[{position}/{len(commune_ids)}] cargo ERA5 commune_id={commune_id}")
        weather_cache[commune_id] = _load_era5_weather(engine, commune_id, year)
    return weather_cache


def _load_regional_hdd(engine, year, base_temperature_c):
    """Load wood-population-weighted HDD from all eligible regional units."""
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
              AND c.cut_region IN (9, 10, 11, 12, 14)
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
                SUM(GREATEST(:base_temperature_c - tmean_c, 0.0))
                    AS hdd
            FROM daily
            GROUP BY codigo_region, commune_id, wood_units
        )
        SELECT
            codigo_region,
            SUM(wood_units) AS wood_units,
            SUM(hdd * wood_units) / SUM(wood_units) AS hdd
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
                "base_temperature_c": float(base_temperature_c),
            },
        )
    if regional.empty:
        raise RuntimeError("No se pudo calcular HDD regional para el stock de lena.")
    return {
        int(row.codigo_region): float(row.hdd)
        for row in regional.itertuples(index=False)
    }


def _climate_severity_parameters(
    regional_hdd, base_temperature_c, enabled
):
    """Build region-level envelope proxies from the selected sample's HDD."""
    neutral = {
        "enabled": False,
        "hdd_base_c": float(base_temperature_c),
        "hdd_regional": np.nan,
        "hdd_reference_c": np.nan,
        "hdd_ratio": np.nan,
        "envelope_factors": {
            "wall_u_multiplier": 1.0,
            "window_u_multiplier": 1.0,
            "infiltration_multiplier": 1.0,
        },
    }
    parameters = {region_code: dict(neutral) for region_code in REGION_NAMES}
    if not enabled:
        return parameters

    hdd_by_region = regional_hdd
    if HDD_REFERENCE_REGION not in hdd_by_region:
        raise RuntimeError(
            f"No se pudo calcular HDD para la region de referencia "
            f"{HDD_REFERENCE_REGION}."
        )
    reference_hdd = hdd_by_region[HDD_REFERENCE_REGION]
    if reference_hdd <= 0:
        raise RuntimeError("El HDD de referencia debe ser positivo.")

    for region_code, hdd in hdd_by_region.items():
        ratio = max(hdd / reference_hdd, 1e-9)
        parameters[region_code] = {
            "enabled": True,
            "hdd_base_c": float(base_temperature_c),
            "hdd_regional": hdd,
            "hdd_reference_c": reference_hdd,
            "hdd_ratio": ratio,
            "envelope_factors": {
                "wall_u_multiplier": BASE_WALL_U_MULTIPLIER
                * ratio**HDD_WALL_EXPONENT,
                "window_u_multiplier": BASE_WINDOW_U_MULTIPLIER
                * ratio**HDD_WINDOW_EXPONENT,
                "infiltration_multiplier": BASE_INFILTRATION_MULTIPLIER
                * ratio**HDD_INFILTRATION_EXPONENT,
            },
        }
    return parameters


def _scenario_row(building, model, year, efficiency, scenario, target_fuel, **extra):
    heating_load = model.detailedResults["Heating Load"]
    demand_kwh = float(heating_load.sum())
    result = tsib.simulate_wood_stove_from_5r1c(
        model,
        fuel_energy_target_kwh=target_fuel,
        efficiency=efficiency,
    )
    row = {
        "edificio_id": int(building["edificio_id"]),
        "regional_sample_rank": int(building["regional_sample_rank"]),
        "codigo_region": int(building["codigo_region"]),
        "region": REGION_NAMES.get(int(building["codigo_region"]), "unknown"),
        "codigo_comuna": int(building["codigo_comuna"]),
        "tmy_commune_id": int(building["tmy_commune_id"]),
        "nombre_comuna": building["nombre_comuna"],
        "year": int(year),
        "episcope_archetype": building["episcope_archetype"],
        "area_promedio_inmueble_m2": float(building["area_promedio_inmueble"]),
        "n_inmuebles": (
            int(building["n_inmuebles"])
            if pd.notna(building["n_inmuebles"])
            else 1
        ),
        "total_inmuebles_regional": int(building["total_inmuebles_regional"]),
        "wood_inmuebles_regional": int(building["wood_inmuebles_regional"]),
        "wood_share_regional": float(building["wood_share_regional"]),
        "sampling_weight_wood_inmuebles": float(
            building["sampling_weight_wood_inmuebles"]
        )
        if pd.notna(building["sampling_weight_wood_inmuebles"])
        else np.nan,
        "sample_expansion_weight": float(building["sample_expansion_weight"]),
        "requested_samples_region": int(building["requested_samples"]),
        "n_pers_edificio": (
            float(building["n_pers_edificio"])
            if pd.notna(building["n_pers_edificio"])
            else np.nan
        ),
        "heating_demand_kwh": demand_kwh,
        "heating_demand_kwh_m2": demand_kwh
        / float(building["area_promedio_inmueble"]),
        "scenario": scenario,
        "efficiency": efficiency,
        "target_fuel_energy_kwh": float(target_fuel),
        "assigned_useful_energy_kwh": result.assigned_useful_energy_kwh,
        "assigned_fuel_energy_kwh": result.assigned_fuel_energy_kwh,
        "unallocated_fuel_energy_kwh": result.unallocated_fuel_energy_kwh,
        "unmet_heating_energy_kwh": result.unmet_heating_energy_kwh,
        "wood_mass_kg": result.wood_mass_kg,
        "wood_volume_solid_m3": result.wood_volume_solid_m3,
        "wood_volume_stere": result.wood_volume_stere,
    }
    row.update(extra)
    return row


def _simulate_building(
    building, weather, year, efficiency, severity_parameters=None
):
    region_code = int(building["codigo_region"])
    severity = (severity_parameters or {}).get(region_code)
    if severity is None:
        severity = {
            "enabled": False,
            "hdd_base_c": np.nan,
            "hdd_regional": np.nan,
            "hdd_reference_c": np.nan,
            "hdd_ratio": np.nan,
            "envelope_factors": {
                "wall_u_multiplier": 1.0,
                "window_u_multiplier": 1.0,
                "infiltration_multiplier": 1.0,
            },
        }
    model, archetype, persons, area_m2 = _build_model(
        building,
        weather,
        envelope_factors=(
            severity["envelope_factors"] if severity["enabled"] else None
        ),
    )
    heating_load = model.detailedResults["Heating Load"]
    demand_kwh = float(heating_load.sum())
    rows = []
    severity_extra = {
        "climate_severity_adjustment": bool(severity["enabled"]),
        "hdd_base_c": severity["hdd_base_c"],
        "hdd_regional": severity["hdd_regional"],
        "hdd_reference_region": HDD_REFERENCE_REGION,
        "hdd_reference_c": severity["hdd_reference_c"],
        "hdd_ratio_to_reference": severity["hdd_ratio"],
        "wall_u_multiplier": severity["envelope_factors"]["wall_u_multiplier"],
        "window_u_multiplier": severity["envelope_factors"]["window_u_multiplier"],
        "infiltration_multiplier": severity["envelope_factors"][
            "infiltration_multiplier"
        ],
    }

    coverage = 0.75
    coverage_target = demand_kwh * coverage / efficiency
    rows.append(
        _scenario_row(
            building,
            model,
            year,
            efficiency,
            "coverage_mid",
            coverage_target,
            scenario_source="coverage_sensitivity",
            useful_coverage_target=coverage,
            redpe_case=None,
            redpe_target_m3st=np.nan,
            weather_rows=len(weather),
            building_year=archetype["building_year"],
            building_type=archetype["building_type"],
            material=archetype["material"],
            thermal_zone=archetype["thermal_zone"],
            model_persons=persons,
            model_area_m2=area_m2,
            **severity_extra,
        )
    )

    try:
        redpe = tsib.get_chile_regional_wood_consumption(
            int(building["codigo_region"]), "mid"
        )
    except ValueError:
        redpe = None
    if redpe is not None:
        rows.append(
            _scenario_row(
                building,
                model,
                year,
                efficiency,
                "redpe_mid",
                float(redpe["energy_bruta_mwh_per_consumer"]) * 1000.0,
                scenario_source="REDPE_2020",
                useful_coverage_target=np.nan,
                redpe_case="mid",
                redpe_target_m3st=float(redpe["consumption_m3st_per_consumer"]),
                weather_rows=len(weather),
                building_year=archetype["building_year"],
                building_type=archetype["building_type"],
                material=archetype["material"],
                thermal_zone=archetype["thermal_zone"],
                model_persons=persons,
                model_area_m2=area_m2,
                **severity_extra,
            )
        )
    return rows


def _summary_table(results):
    value_columns = [
        "heating_demand_kwh",
        "heating_demand_kwh_m2",
        "target_fuel_energy_kwh",
        "assigned_fuel_energy_kwh",
        "unallocated_fuel_energy_kwh",
        "wood_volume_stere",
        "unmet_heating_energy_kwh",
        "redpe_target_m3st",
    ]
    rows = []
    for (region_code, region, scenario), group in results.groupby(
        ["codigo_region", "region", "scenario"], dropna=False
    ):
        row = {
            "codigo_region": int(region_code),
            "region": region,
            "scenario": scenario,
            "n_simulations": int(len(group)),
            "n_inmuebles_sampled": int(group["n_inmuebles"].sum()),
            "total_inmuebles_regional": int(group["total_inmuebles_regional"].iloc[0]),
            "wood_inmuebles_regional": int(group["wood_inmuebles_regional"].iloc[0]),
            "wood_share_regional": float(group["wood_share_regional"].iloc[0]),
            "sampling_weight_wood_inmuebles": float(
                group["sampling_weight_wood_inmuebles"].iloc[0]
            ),
            "sample_expansion_weight": float(
                group["sample_expansion_weight"].iloc[0]
            ),
        }
        for column in value_columns:
            series = pd.to_numeric(group[column], errors="coerce")
            weights = (
                pd.to_numeric(group["n_inmuebles"], errors="coerce")
                .fillna(1.0)
                .clip(lower=1.0)
            )
            row[f"{column}_min"] = float(series.min())
            row[f"{column}_p10"] = float(series.quantile(0.10))
            row[f"{column}_median"] = float(series.median())
            row[f"{column}_p90"] = float(series.quantile(0.90))
            row[f"{column}_max"] = float(series.max())
            row[f"{column}_std"] = float(series.std(ddof=1)) if len(series) > 1 else 0.0
            row[f"{column}_weighted_mean"] = float(
                np.average(series.to_numpy(dtype=float), weights=weights.to_numpy(dtype=float))
            )
        redpe_target = pd.to_numeric(
            group["redpe_target_m3st"], errors="coerce"
        ).dropna()
        row["redpe_mid_target_m3st"] = (
            float(redpe_target.iloc[0]) if not redpe_target.empty else np.nan
        )
        simulated_volume = row["wood_volume_stere_weighted_mean"]
        row["wood_volume_to_redpe_mid_ratio"] = (
            simulated_volume / row["redpe_mid_target_m3st"]
            if np.isfinite(row["redpe_mid_target_m3st"])
            and row["redpe_mid_target_m3st"] > 0
            else np.nan
        )
        row["relative_error_to_redpe_mid"] = (
            row["wood_volume_to_redpe_mid_ratio"] - 1.0
            if np.isfinite(row["wood_volume_to_redpe_mid_ratio"])
            else np.nan
        )
        row["climate_severity_adjustment"] = bool(
            group["climate_severity_adjustment"].iloc[0]
        )
        row["hdd_base_c"] = float(group["hdd_base_c"].iloc[0])
        row["hdd_regional"] = float(group["hdd_regional"].iloc[0])
        row["hdd_ratio_to_reference"] = float(
            group["hdd_ratio_to_reference"].iloc[0]
        )
        row["wall_u_multiplier"] = float(group["wall_u_multiplier"].iloc[0])
        row["window_u_multiplier"] = float(
            group["window_u_multiplier"].iloc[0]
        )
        row["infiltration_multiplier"] = float(
            group["infiltration_multiplier"].iloc[0]
        )
        median_demand = row["heating_demand_kwh_median"]
        row["heating_demand_cv"] = (
            row["heating_demand_kwh_std"] / median_demand
            if median_demand
            else np.nan
        )
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["codigo_region", "scenario"])


def _write_report(output_dir, args, buildings, results, summary, errors):
    counts = (
        buildings.groupby("codigo_region", dropna=False)
        .size()
        .reset_index(name="n_selected")
        .sort_values("codigo_region")
    )
    sampling_description = (
        "Muestreo determinista y estratificado por comuna con cuota fija por región."
        if args.samples_per_region is not None
        else (
            "Muestreo determinista y estratificado por comuna; cuota proporcional "
            f"a unidades con calefaccion a lena, con piso de "
            f"`{args.minimum_samples_per_region}` por region."
        )
    )
    lines = [
        "# Dispersion regional de simulaciones de estufa a lena",
        "",
        "## Configuracion",
        "",
        f"- Ano meteorologico: `{args.year}`.",
        f"- Muestra solicitada: `{args.total_samples if args.samples_per_region is None else args.samples_per_region}` registros `edificio_id`, semilla `{args.seed}`.",
        f"- Eficiencia de estufa: `{args.efficiency:.2f}`.",
        (
            f"- Severidad climatica: HDD base `{args.hdd_base_c:.1f} C`, "
            "aplicada a Araucania, Los Rios, Los Lagos, Aysen y Magallanes; "
            "los exponentes amortiguan la doble contabilizacion con la "
            "temperatura que ya usa 5R1C."
            if args.apply_climate_severity
            else "- Severidad climatica: sin ajuste; corrida base."
        ),
        f"- {sampling_description} La prevalencia se reporta como unidades a lena sobre el stock regional elegible.",
        "- Un `edificio_id` puede representar varias unidades habitacionales; por eso se conserva `n_inmuebles` y el factor de expansion regional.",
        "- Escenario comparable: `coverage_mid`, 75% de cobertura util de calefaccion.",
        "- Escenario complementario: `redpe_mid`, solo para regiones con fila REDPE 2020.",
        "",
        "## Cobertura de la muestra",
        "",
        "| Codigo | Region | Stock regional | Inmuebles a lena | Participacion lena | Muestra |",
        "|---:|---|---:|---:|---:|---:|",
    ]
    allocation_view = (
        buildings[
            [
                "codigo_region",
                "total_inmuebles_regional",
                "wood_inmuebles_regional",
                "wood_share_regional",
                "requested_samples",
            ]
        ]
        .drop_duplicates("codigo_region")
        .merge(counts, on="codigo_region", how="left")
        .sort_values("codigo_region")
    )
    allocation_view["region"] = allocation_view["codigo_region"].map(REGION_NAMES)
    for row in allocation_view.itertuples(index=False):
        lines.append(
            f"| {int(row.codigo_region)} | {row.region} | "
            f"{int(row.total_inmuebles_regional)} | "
            f"{int(row.wood_inmuebles_regional)} | "
            f"{row.wood_share_regional:.3%} | {int(row.n_selected)} |"
        )

    coverage_summary = summary[summary["scenario"] == "coverage_mid"]
    lines.extend(
        [
            "",
            "## Dispersion de demanda termica",
            "",
            "Valores en kWh por registro `edificio_id`; P10 y P90 muestran la amplitud central de la muestra.",
            "",
            "| Region | n | Demanda P10 | Mediana | Demanda P90 | CV mediana | Volumen leña P10-P90 (st) |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in coverage_summary.itertuples(index=False):
        lines.append(
            f"| {row.region} | {row.n_simulations} | "
            f"{row.heating_demand_kwh_p10:.1f} | {row.heating_demand_kwh_median:.1f} | "
            f"{row.heating_demand_kwh_p90:.1f} | {row.heating_demand_cv:.2f} | "
            f"{row.wood_volume_stere_p10:.2f}-{row.wood_volume_stere_p90:.2f} |"
        )

    redpe_regions = summary[summary["scenario"] == "redpe_mid"]["region"].tolist()
    redpe_summary = summary[summary["scenario"] == "redpe_mid"]
    lines.extend(
        [
            "",
            "## REDPE",
            "",
            "`redpe_mid` se calculo para: "
            + (", ".join(redpe_regions) if redpe_regions else "ninguna region")
            + ". Las regiones sin fila REDPE se mantienen en el escenario comparable de cobertura.",
        ]
    )
    if not redpe_summary.empty:
        lines.extend(
            [
                "",
                "### Comparacion ponderada contra REDPE_mid",
                "",
                "El valor simulado es la media ponderada por `n_inmuebles` de los registros seleccionados.",
                "",
                "| Region | REDPE_mid (m3 st/a) | Simulado (m3 st/a) | Ratio | Error relativo |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for row in redpe_summary.itertuples(index=False):
            lines.append(
                f"| {row.region} | {row.redpe_mid_target_m3st:.3f} | "
                f"{row.wood_volume_stere_weighted_mean:.3f} | "
                f"{row.wood_volume_to_redpe_mid_ratio:.3f} | "
                f"{row.relative_error_to_redpe_mid:.1%} |"
            )
    if args.apply_climate_severity:
        severity_summary = (
            summary[summary["climate_severity_adjustment"]]
            .drop_duplicates("codigo_region")
            .sort_values("codigo_region")
        )
        lines.extend(
            [
                "",
                "### Factores de severidad climatica",
                "",
                "HDD calculados con temperatura media diaria y ponderacion por el stock elegible regional.",
                "",
                "| Region | HDD base 12 C | HDD regional | HDD/ref. | U muros | U ventanas | Infiltracion |",
                "|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for row in severity_summary.itertuples(index=False):
            lines.append(
                f"| {row.region} | {row.hdd_base_c:.1f} | {row.hdd_regional:.1f} | "
                f"{row.hdd_ratio_to_reference:.3f} | {row.wall_u_multiplier:.3f} | "
                f"{row.window_u_multiplier:.3f} | {row.infiltration_multiplier:.3f} |"
            )
    if errors:
        lines.extend(
            [
                "",
                "## Errores",
                "",
                f"Se registraron `{len(errors)}` errores. Ver `simulation_errors.csv` para el detalle.",
            ]
        )
    else:
        lines.extend(["", "No se registraron errores de simulacion."])
    (output_dir / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    args = _parse_args()
    _load_env_file(args.env_file)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    engine = _create_engine()
    buildings = _load_sampled_buildings(
        engine,
        args.total_samples,
        args.seed,
        samples_per_region=args.samples_per_region,
        minimum_samples_per_region=args.minimum_samples_per_region,
    )
    buildings.to_csv(args.output_dir / "selected_buildings.csv", index=False)
    allocation = (
        buildings[
            [
                "codigo_region",
                "total_inmuebles_regional",
                "wood_inmuebles_regional",
                "total_records_regional",
                "wood_records_regional",
                "wood_share_regional",
                "sampling_weight_wood_inmuebles",
                "requested_samples",
            ]
        ]
        .drop_duplicates("codigo_region")
        .copy()
    )
    selected_counts = (
        buildings.groupby("codigo_region")
        .size()
        .rename("selected_records")
        .reset_index()
    )
    allocation = allocation.merge(
        selected_counts, on="codigo_region", how="left", validate="one_to_one"
    )
    allocation.to_csv(
        args.output_dir / "regional_sampling_allocation.csv", index=False
    )

    regional_hdd = (
        _load_regional_hdd(engine, args.year, args.hdd_base_c)
        if args.apply_climate_severity
        else {}
    )
    weather_cache = _load_weather_cache(engine, buildings, args.year)
    severity_parameters = _climate_severity_parameters(
        regional_hdd,
        args.hdd_base_c,
        args.apply_climate_severity,
    )
    severity_rows = []
    for region_code in sorted(SEVERITY_REGIONS):
        severity = severity_parameters.get(region_code)
        if severity is None or not severity["enabled"]:
            continue
        severity_rows.append(
            {
                "codigo_region": region_code,
                "region": REGION_NAMES[region_code],
                "hdd_base_c": severity["hdd_base_c"],
                "hdd_regional": severity["hdd_regional"],
                "hdd_reference_region": HDD_REFERENCE_REGION,
                "hdd_reference_c": severity["hdd_reference_c"],
                "hdd_ratio_to_reference": severity["hdd_ratio"],
                **severity["envelope_factors"],
            }
        )
    pd.DataFrame(
        severity_rows,
        columns=[
            "codigo_region",
            "region",
            "hdd_base_c",
            "hdd_regional",
            "hdd_reference_region",
            "hdd_reference_c",
            "hdd_ratio_to_reference",
            "wall_u_multiplier",
            "window_u_multiplier",
            "infiltration_multiplier",
        ],
    ).to_csv(args.output_dir / "regional_climate_severity.csv", index=False)

    result_rows = []
    errors = []
    for position, building in enumerate(buildings.to_dict("records"), start=1):
        commune_id = int(building["tmy_commune_id"])
        try:
            rows = _simulate_building(
                building,
                weather_cache[commune_id],
                args.year,
                args.efficiency,
                severity_parameters=severity_parameters,
            )
            result_rows.extend(rows)
            print(
                f"[{position}/{len(buildings)}] edificio_id={building['edificio_id']} "
                f"region={building['codigo_region']} demand="
                f"{rows[0]['heating_demand_kwh']:.1f} kWh"
            )
        except Exception as error:  # keep the regional batch auditable
            errors.append(
                {
                    "edificio_id": int(building["edificio_id"]),
                    "codigo_region": int(building["codigo_region"]),
                    "codigo_comuna": int(building["codigo_comuna"]),
                    "tmy_commune_id": commune_id,
                    "error_type": type(error).__name__,
                    "error": str(error),
                }
            )
            print(
                f"[{position}/{len(buildings)}] ERROR edificio_id="
                f"{building['edificio_id']}: {error}"
            )

    if not result_rows:
        raise RuntimeError("No se completo ninguna simulacion.")
    results = pd.DataFrame(result_rows)
    summary = _summary_table(results)
    results.to_csv(args.output_dir / "simulation_results.csv", index=False)
    summary.to_csv(args.output_dir / "regional_summary.csv", index=False)
    pd.DataFrame(errors, columns=ERROR_COLUMNS).to_csv(
        args.output_dir / "simulation_errors.csv", index=False
    )
    _write_report(args.output_dir, args, buildings, results, summary, errors)

    print(f"Simulaciones completadas: {results['edificio_id'].nunique()}")
    print(f"Escenarios generados: {len(results)}")
    print(f"Errores: {len(errors)}")
    print(summary.to_string(index=False, float_format=lambda value: f"{value:.3f}"))
    print(f"Resultados: {args.output_dir}")


if __name__ == "__main__":
    main()
